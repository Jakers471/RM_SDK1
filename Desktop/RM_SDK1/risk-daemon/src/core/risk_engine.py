"""
RiskEngine - Central risk evaluation and enforcement orchestrator.

Responsibilities:
- Receive events from event bus
- Evaluate all rules against current state
- Detect violations
- Trigger enforcement actions
- Handle cascading rule violations

Architecture reference: docs/architecture/02-risk-engine.md
"""

from typing import List, Optional
from datetime import datetime

from src.rules.base_rule import RiskRule
from src.state.models import RuleViolation


class RiskEngine:
    """
    Central risk engine that evaluates rules and triggers enforcement.

    Flow:
    1. Receive event
    2. Check lockout status (early exit if locked out)
    3. Evaluate all applicable rules
    4. Execute enforcement actions
    5. Re-evaluate rules after enforcement (cascading)
    """

    def __init__(
        self,
        state_manager,
        enforcement_engine,
        rules: List[RiskRule],
        monitors: Optional[List] = None
    ):
        """
        Initialize risk engine.

        Args:
            state_manager: State manager instance
            enforcement_engine: Enforcement engine instance
            rules: List of risk rules to evaluate
            monitors: Optional list of monitors (e.g., StopLossDetector)
        """
        self.state_manager = state_manager
        self.enforcement_engine = enforcement_engine
        self.rules = rules
        self.monitors = monitors or []

    async def process_event(self, event):
        """
        Process event through risk engine.

        Args:
            event: Event object with event_type, account_id, data, etc.
        """
        account_id = event.account_id

        # Handle TIME_TICK events specially - evaluate for all accounts
        if event.event_type == "TIME_TICK":
            # Run monitors for all accounts on TIME_TICK
            for acc_id in list(self.state_manager.accounts.keys()):
                account_state = self.state_manager.get_account_state(acc_id)
                await self._process_monitors(event, account_state)
                await self._evaluate_rules_for_account(acc_id, event)
            return

        # Get account state
        account_state = self.state_manager.get_account_state(account_id)

        # Process monitors first (before creating position for FILL events)
        # This allows monitors to update flags on existing positions
        await self._process_monitors(event, account_state)

        # Handle FILL event (create position)
        if event.event_type == "FILL":
            await self._handle_fill_event(event, account_state)

        # Early exit if account is locked out
        if self.state_manager.is_locked_out(account_id):
            # If this is a FILL event during lockout, close it immediately
            if event.event_type == "FILL":
                # Close the position that was just filled
                positions = self.state_manager.get_open_positions(account_id)
                if positions:
                    most_recent = max(positions, key=lambda p: p.opened_at)
                    await self.enforcement_engine.close_position(
                        account_id=account_id,
                        position_id=most_recent.position_id,
                        quantity=None,
                        reason="Account locked out - rejecting new fill"
                    )
            return

        # Evaluate rules for this account
        await self._evaluate_rules_for_account(account_id, event)

    async def _evaluate_rules_for_account(self, account_id: str, event):
        """
        Evaluate all rules for a specific account.

        Args:
            account_id: Account ID to evaluate
            event: Event that triggered evaluation
        """
        # Get account state
        account_state = self.state_manager.get_account_state(account_id)

        # Evaluate all applicable rules
        violations = []
        for rule in self.rules:
            if not rule.enabled:
                continue

            if not rule.applies_to_event(event.event_type):
                continue

            violation = rule.evaluate(event.data, account_state)
            if violation:
                violations.append((rule, violation))

        # Execute enforcement actions for violations
        for rule, violation in violations:
            action = rule.get_enforcement_action(violation)
            await self.enforcement_engine.execute_action(action)

            # After enforcement, check for cascading violations
            # (e.g., closing position for per-trade limit might trigger daily limit)
            await self._check_cascading_violations(account_id, rule)

    async def _process_monitors(self, event, account_state):
        """
        Process event through all monitors.

        Monitors can update position flags or state based on events.

        Args:
            event: Event to process
            account_state: Current account state
        """
        for monitor in self.monitors:
            # Check if monitor applies to this event type
            if hasattr(monitor, 'applies_to_event'):
                if not monitor.applies_to_event(event.event_type):
                    continue

            # Process the event through the monitor
            if event.event_type in ["ORDER", "ORDER_STATUS"]:
                # For order events, call process_order if available
                if hasattr(monitor, 'process_order'):
                    monitor.process_order(event.data, account_state)

    async def _handle_fill_event(self, event, account_state):
        """
        Handle FILL event by adding position to state.

        Args:
            event: FILL event
            account_state: Account state
        """
        from uuid import uuid4
        from src.state.state_manager import Position
        from decimal import Decimal
        from datetime import timedelta

        # Create new position from fill data
        position = Position(
            position_id=uuid4(),
            account_id=account_state.account_id,
            symbol=event.data["symbol"],
            side=event.data["side"],
            quantity=event.data["quantity"],
            entry_price=event.data["fill_price"],
            current_price=event.data["fill_price"],
            unrealized_pnl=Decimal("0.0"),
            opened_at=event.timestamp,
            stop_loss_attached=False,
            stop_loss_grace_expires=None
        )

        # Check if NoStopLossGrace rule is enabled and set grace period
        for rule in self.rules:
            if hasattr(rule, 'name') and rule.name == "NoStopLossGrace" and rule.enabled:
                # Set grace period expiration
                grace_seconds = getattr(rule, 'grace_period_seconds', 120)
                position.stop_loss_grace_expires = event.timestamp + timedelta(seconds=grace_seconds)
                break

        self.state_manager.add_position(account_state.account_id, position)

    async def _check_cascading_violations(self, account_id: str, triggered_rule: RiskRule):
        """
        Check for cascading rule violations after enforcement.

        Example: Per-trade rule closes position → realized PnL updated →
                 daily limit rule might now be violated.

        Args:
            account_id: Account ID
            triggered_rule: Rule that just triggered enforcement
        """
        # Get updated account state
        account_state = self.state_manager.get_account_state(account_id)

        # Evaluate all rules again (except the one that just triggered)
        for rule in self.rules:
            if rule == triggered_rule:
                continue

            if not rule.enabled:
                continue

            # Evaluate with empty event data (post-enforcement check)
            violation = rule.evaluate({}, account_state)
            if violation:
                action = rule.get_enforcement_action(violation)
                await self.enforcement_engine.execute_action(action)
