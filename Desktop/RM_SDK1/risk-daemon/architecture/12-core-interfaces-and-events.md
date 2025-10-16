# Core Interfaces and Events

## Overview

This document defines the **SDK-agnostic** core data structures and event types for the Risk Manager Daemon. These interfaces form the contracts between components (Event Bus, Risk Engine, State Manager, Enforcement Engine). **No SDK-specific types or method names appear here** - those are defined by the SDK Analyst in `docs/integration/`.

---

## Core Data Structures

### Event

The universal event container flowing through the Event Bus.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Any, Optional
from uuid import UUID

@dataclass
class Event:
    """
    Universal event type. All events entering the system are normalized to this structure.
    """
    # Event metadata
    event_id: UUID                  # Unique identifier for this event (deterministic ordering)
    event_type: EventType           # See EventType enum below
    timestamp: datetime             # When event occurred (UTC)
    priority: int                   # Processing priority (1=highest, 6=lowest)

    # Context
    account_id: str                 # Which account this event relates to
    source: str                     # Event source (e.g., "broker", "timer", "config", "admin")

    # Event-specific data
    data: dict[str, Any]            # Event-specific payload (varies by event_type)

    # Tracing
    correlation_id: Optional[UUID] = None  # Links related events (e.g., order → fill)
```

---

### EventType

Enumeration of all event types the system emits and consumes.

```python
from enum import Enum

class EventType(Enum):
    """All event types in the system with processing priorities."""

    # Priority 1: Connection events (highest - handle immediately)
    CONNECTION_CHANGE = (1, "connection_change")

    # Priority 2: Trading events (core business logic)
    FILL = (2, "fill")                          # New position opened or added to
    ORDER_UPDATE = (2, "order_update")          # Order status changed
    POSITION_UPDATE = (2, "position_update")    # Position price/PnL changed

    # Priority 3: Configuration events
    CONFIG_RELOAD = (3, "config_reload")        # Configuration hot-reloaded

    # Priority 4: Timer events
    TIME_TICK = (4, "time_tick")                # 1-second interval tick

    # Priority 5: Session events
    SESSION_TICK = (5, "session_tick")          # Session boundary or daily reset

    # Priority 6: Health monitoring (lowest priority)
    HEARTBEAT = (6, "heartbeat")                # System health check

    def __init__(self, priority: int, value: str):
        self._priority = priority
        self._value = value

    @property
    def priority(self) -> int:
        return self._priority
```

**Priority Processing Rules**:
- Events with **lower priority number** are processed first
- Events with **same priority** are ordered by `timestamp`, then `event_id`
- Single-threaded queue ensures deterministic ordering

---

### AccountState

Current state for a single trading account.

```python
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

@dataclass
class AccountState:
    """
    Runtime state for a single account. Single source of truth for risk evaluation.
    """
    # Identity
    account_id: str
    account_name: str

    # Positions
    open_positions: list['Position'] = field(default_factory=list)

    # PnL tracking
    realized_pnl_today: Decimal = Decimal('0.00')      # Closed positions PnL (since last 5pm CT)
    total_unrealized_pnl: Decimal = Decimal('0.00')    # Sum of all open positions unrealized PnL

    # Lockout and cooldown
    lockout_until: Optional[datetime] = None           # If locked out, when it expires
    cooldown_until: Optional[datetime] = None          # If in cooldown, when it expires

    # Trade frequency tracking
    trade_frequency_windows: dict[str, 'FrequencyWindow'] = field(default_factory=dict)

    # Daily reset tracking
    last_daily_reset: datetime = field(default_factory=datetime.utcnow)

    # Error state
    error_state: bool = False                          # True if critical error occurred
    error_message: Optional[str] = None

    # Computed properties (not stored, calculated on-demand)
    @property
    def combined_exposure(self) -> Decimal:
        """Realized + Unrealized PnL (critical for daily limit checks)."""
        return self.realized_pnl_today + self.total_unrealized_pnl

    @property
    def is_locked_out(self) -> bool:
        """Is account currently locked out from trading?"""
        if self.lockout_until is None:
            return False
        return datetime.utcnow() < self.lockout_until

    @property
    def is_in_cooldown(self) -> bool:
        """Is account currently in cooldown period?"""
        if self.cooldown_until is None:
            return False
        return datetime.utcnow() < self.cooldown_until

    @property
    def position_count(self) -> int:
        """Total number of contracts across all positions."""
        return sum(pos.quantity for pos in self.open_positions)

    def get_position_count_by_symbol(self, symbol: str) -> int:
        """Contract count for a specific symbol."""
        return sum(pos.quantity for pos in self.open_positions if pos.symbol == symbol)
```

---

### Position

Represents an open position in a trading account.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

@dataclass
class Position:
    """
    Single open position (long or short) in an instrument.
    Minimal required fields - SDK Adapter populates these from broker data.
    """
    # Identity
    position_id: UUID                           # Unique identifier
    account_id: str                             # Which account owns this
    symbol: str                                 # Instrument symbol (e.g., "MNQ", "ES")
    side: Literal["long", "short"]              # Position direction

    # Size and pricing
    quantity: int                               # Number of contracts
    entry_price: Decimal                        # Average entry price
    current_price: Decimal                      # Last known mark/last price

    # PnL
    unrealized_pnl: Decimal                     # Current floating PnL (calculated)

    # Timestamps
    opened_at: datetime                         # When position opened
    last_update: datetime                       # Last price update

    # Risk management metadata
    pending_close: bool = False                 # True if close order sent but not confirmed
    stop_loss_attached: bool = False            # True if stop loss order detected
    stop_loss_price: Optional[Decimal] = None   # Stop loss price (if known)
    stop_loss_grace_expires: Optional[datetime] = None  # NoStopLossGrace timer

    def calculate_unrealized_pnl(self, tick_value: Decimal) -> Decimal:
        """
        Calculate unrealized PnL given current_price and tick_value.
        Formula:
            Long:  (current_price - entry_price) * quantity * tick_value
            Short: (entry_price - current_price) * quantity * tick_value

        tick_value: Dollar value per 1-point move per contract (e.g., $5 for MNQ)
        """
        if self.side == "long":
            pnl = (self.current_price - self.entry_price) * self.quantity * tick_value
        else:  # short
            pnl = (self.entry_price - self.current_price) * self.quantity * tick_value

        return pnl.quantize(Decimal('0.01'))  # Round to cents
```

---

### FrequencyWindow

Tracks trade count for TradeFrequencyLimit rule.

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class FrequencyWindow:
    """
    Time window for tracking trade frequency (e.g., 3 trades per day, 1 per 15min).
    """
    rule_id: str                    # Which rule this window belongs to
    window_start: datetime          # When current window started
    window_duration: timedelta      # How long window lasts (e.g., 1 day, 15 minutes)
    trade_count: int                # Trades executed in this window
    resets_at: datetime             # When window resets

    def is_expired(self) -> bool:
        """Has this window expired and needs reset?"""
        return datetime.utcnow() >= self.resets_at

    def reset(self) -> None:
        """Reset window to fresh state."""
        self.window_start = datetime.utcnow()
        self.trade_count = 0
        self.resets_at = self.window_start + self.window_duration
```

---

## Risk Rule Interface

### RiskRulePlugin

Base interface all risk rules implement.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

class RiskRulePlugin(ABC):
    """
    Base interface for all risk rules. Each rule is a self-contained plugin.
    """

    # Metadata (class attributes)
    name: str              # e.g., "MaxContracts"
    version: str           # e.g., "1.0.0"
    description: str       # Human-readable description
    author: str = "Risk Manager Daemon"

    # Configuration schema (subclass defines)
    config_schema: dict    # JSON schema for rule parameters

    def __init__(self, params: dict):
        """
        Initialize rule with configured parameters.
        Subclass validates params against config_schema.
        """
        self.params = params
        self.validate_params()

    @abstractmethod
    def validate_params(self) -> None:
        """Validate params match config_schema. Raise ValueError if invalid."""
        pass

    @abstractmethod
    def applies_to_event(self, event_type: EventType) -> bool:
        """Does this rule care about this event type?"""
        pass

    @abstractmethod
    def evaluate(self, event: Event, state: AccountState) -> Optional['RuleViolation']:
        """
        Evaluate rule against event and current account state.
        Returns RuleViolation if rule breached, None if OK.
        """
        pass

    @abstractmethod
    def get_enforcement_action(self, violation: 'RuleViolation') -> 'EnforcementAction':
        """Determine what action to take given a violation."""
        pass
```

---

### RuleViolation

Represents a rule breach detected by a risk rule.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Any, Optional
from uuid import UUID

@dataclass
class RuleViolation:
    """
    Rule violation detected during evaluation.
    """
    # Which rule was violated
    rule_name: str
    rule_version: str

    # Severity (used for prioritization if multiple rules violated)
    severity: Literal["critical", "warning", "info"]

    # Violation details
    message: str                        # Human-readable explanation
    current_value: Any                  # What triggered violation (e.g., contract count, PnL)
    limit_value: Any                    # What the limit was
    exceeded_by: Optional[Any] = None   # How much over limit (if applicable)

    # Context
    account_id: str
    event_id: UUID                      # Which event triggered this
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Associated position (if violation is position-specific)
    position_id: Optional[UUID] = None
    symbol: Optional[str] = None
```

---

### EnforcementAction

Action to be taken by Enforcement Engine.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

@dataclass
class EnforcementAction:
    """
    Action to execute in response to a rule violation.
    """
    # Action type
    action_type: Literal[
        "close_position",       # Close specific position (partial or full)
        "flatten_account",      # Close all positions
        "set_lockout",          # Block trading until specified time
        "start_cooldown",       # Temporary trading pause
        "send_alert"            # Notification only, no position action
    ]

    # Context
    account_id: str
    rule_name: str              # Which rule triggered this action
    reason: str                 # Why action taken (for logging/notification)
    violation: RuleViolation    # The violation that triggered this

    # Action-specific parameters
    position_id: Optional[UUID] = None              # For close_position
    quantity: Optional[int] = None                  # For partial close_position
    lockout_until: Optional[datetime] = None        # For set_lockout
    cooldown_duration: Optional[int] = None         # For start_cooldown (seconds)
    alert_message: Optional[str] = None             # For send_alert
    alert_severity: Optional[Literal["info", "warning", "critical"]] = None

    # Result tracking (populated by Enforcement Engine after execution)
    executed_at: Optional[datetime] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    order_id: Optional[str] = None                  # Broker order ID (if applicable)
```

---

## Event Definitions

### Event Types We Emit/Consume

#### 1. CONNECTION_CHANGE (Priority 1)

**When**: Broker connection status changes (connected, disconnected, reconnected)

**event.data**:
```python
{
    "status": str,              # "connected", "disconnected", "reconnecting"
    "reason": Optional[str],    # Reason for disconnect (if applicable)
    "broker": str               # Broker name (e.g., "topstepx")
}
```

**Triggers**:
- AuthLossGuard rule (alert only)
- State Manager: May set error_state if critical

---

#### 2. FILL (Priority 2)

**When**: New position opened or added to existing position

**event.data**:
```python
{
    "symbol": str,              # Instrument symbol
    "side": str,                # "long" or "short"
    "quantity": int,            # Contracts filled
    "fill_price": Decimal,      # Execution price
    "order_id": str,            # Broker order ID
    "fill_time": datetime       # When fill occurred (broker time)
}
```

**Triggers**:
- MaxContracts
- MaxContractsPerInstrument
- SymbolBlock
- TradeFrequencyLimit
- SessionBlockOutside
- NoStopLossGrace (start timer)
- State Manager: add_position()

---

#### 3. ORDER_UPDATE (Priority 2)

**When**: Order status changes (placed, working, filled, cancelled, rejected)

**event.data**:
```python
{
    "order_id": str,                        # Broker order ID
    "symbol": str,                          # Instrument
    "order_type": str,                      # "market", "limit", "stop"
    "status": str,                          # "working", "filled", "cancelled", "rejected"
    "stop_loss_attached": Optional[bool],   # True if this order has SL attached
    "stop_loss_price": Optional[Decimal],   # SL price if known
    "quantity": int,                        # Order quantity
    "filled_quantity": int                  # How much filled so far
}
```

**Triggers**:
- NoStopLossGrace (check if stop loss attached)
- State Manager: update position metadata

---

#### 4. POSITION_UPDATE (Priority 2)

**When**: Open position's price or PnL changes (market data update)

**event.data**:
```python
{
    "position_id": UUID,            # Which position
    "symbol": str,                  # Instrument
    "current_price": Decimal,       # New mark/last price
    "unrealized_pnl": Decimal,      # New unrealized PnL (if SDK provides, else we calculate)
    "quantity": int,                # Current quantity (may change if partial close)
    "update_time": datetime         # When price updated
}
```

**Triggers**:
- UnrealizedLoss (per-trade)
- UnrealizedProfit (per-trade)
- DailyRealizedLoss (combined check: realized + unrealized)
- DailyRealizedProfit (combined check: realized + unrealized)
- State Manager: update_position()

---

#### 5. CONFIG_RELOAD (Priority 3)

**When**: Configuration files hot-reloaded (admin triggers via CLI)

**event.data**:
```python
{
    "config_type": str,         # "system", "accounts", "risk_rules", "notifications"
    "changes": dict,            # What changed (summary)
    "reload_time": datetime     # When reload occurred
}
```

**Triggers**:
- Risk Engine: reload active rules
- Config Manager: re-validate and apply
- Notification Service: update channels

---

#### 6. TIME_TICK (Priority 4)

**When**: Every 1 second (timer-based)

**event.data**:
```python
{
    "tick_time": datetime       # Current time (UTC)
}
```

**Triggers**:
- NoStopLossGrace: check if grace period expired
- CooldownAfterLoss: check if cooldown expired
- State Manager: check timer expirations

**Note**: TimeTick is generated internally by daemon, not from broker.

---

#### 7. SESSION_TICK (Priority 5)

**When**: Session boundaries (market open, close, daily 5pm CT reset)

**event.data**:
```python
{
    "tick_type": str,           # "session_open", "session_close", "daily_reset"
    "tick_time": datetime,      # When boundary occurred
    "timezone": str             # "America/Chicago"
}
```

**Triggers**:
- SessionBlockOutside: check if outside allowed session
- State Manager: daily_reset (if tick_type == "daily_reset")
- Risk Engine: clear lockouts on daily_reset

**Note**: SessionTick is generated internally based on configured session times.

---

#### 8. HEARTBEAT (Priority 6)

**When**: Periodic health check (every 30 seconds)

**event.data**:
```python
{
    "daemon_uptime": int,           # Seconds since start
    "event_queue_size": int,        # Pending events in queue
    "memory_usage_mb": float,       # Current memory usage
    "cpu_usage_percent": float      # Current CPU usage
}
```

**Triggers**:
- Logging: system health metrics
- Watchdog: verify daemon alive

**Note**: Heartbeat is internal, lowest priority.

---

## Event Processing Guarantees

### Priority-Based Processing

Events processed in strict priority order:

1. **CONNECTION_CHANGE** (P1) - handle connection issues first
2. **FILL, ORDER_UPDATE, POSITION_UPDATE** (P2) - core trading events
3. **CONFIG_RELOAD** (P3) - apply config changes after live events
4. **TIME_TICK** (P4) - timer checks
5. **SESSION_TICK** (P5) - session boundaries
6. **HEARTBEAT** (P6) - health monitoring

Within same priority:
- Order by `event.timestamp` (ascending)
- Then by `event.event_id` (UUID lexicographic order)

### Deterministic Ordering

Single-threaded event loop ensures:
- Events never processed concurrently
- No race conditions on state
- Predictable, testable behavior

### Event Queue Behavior

- **Bounded queue**: Max 10,000 events (prevent memory overflow)
- **Backpressure**: If queue full, log critical error and alert admin
- **No event dropping**: Every event must be processed or explicitly discarded with reason

---

## Summary for Developer

**To implement event processing, you need to:**

1. **Create these data classes** in `src/state/models.py`
2. **Implement Event Bus** that:
   - Accepts events via `publish(event: Event)`
   - Maintains priority queue
   - Dispatches to handlers in order
   - Guarantees deterministic processing
3. **Implement event handlers** that:
   - Receive `Event` objects
   - Extract `event.data` based on `event.event_type`
   - Update state or trigger rule evaluation
4. **Create event normalizer** in SDK Adapter:
   - Convert broker SDK events → our `Event` type
   - Populate `event.data` with normalized fields

**To implement risk rules, you need to:**

1. **Subclass RiskRulePlugin** for each rule (12 rules total)
2. **Implement interface methods**: `validate_params()`, `applies_to_event()`, `evaluate()`, `get_enforcement_action()`
3. **Return RuleViolation** when rule breached
4. **Return EnforcementAction** specifying what to do

**These interfaces are SDK-agnostic** - no broker-specific types here. SDK Analyst will define how to map broker SDK to these interfaces.
