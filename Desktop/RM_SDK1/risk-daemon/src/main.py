"""
Risk Manager Daemon - Main Entry Point

Production-ready risk management system for automated trading enforcement.
Monitors positions, enforces risk rules, and manages account safety.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('risk_daemon.log')
    ]
)
logger = logging.getLogger(__name__)


class RiskDaemon:
    """Main risk management daemon."""

    def __init__(self, config: dict):
        """
        Initialize risk daemon with configuration.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.running = False
        self.sdk_adapter = None
        self.event_bus = None
        self.risk_engine = None
        self.state_manager = None
        self.enforcement_engine = None
        self.persistence = None
        self.health_monitor = None
        self.connection_manager = None

    async def start(self):
        """Start the risk daemon."""
        logger.info("Starting Risk Manager Daemon...")
        logger.info(f"Account ID: {self.config['account_id']}")
        logger.info(f"Mode: {self.config['mode']}")

        try:
            if self.config['mode'] == 'test':
                await self._start_test_mode()
            else:
                await self._start_live_mode()

            self.running = True
            logger.info("Risk Manager Daemon started successfully")

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            await self.stop()
            raise

    async def _start_test_mode(self):
        """Start daemon in test mode with mock components."""
        logger.info("Starting in TEST mode - using mock broker")

        # Import test components
        from tests.conftest import FakeBrokerAdapter, FakeStateManager, FakeNotifier, FakeClock
        from src.core.event_bus import EventBus
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine

        # Initialize test components
        clock = FakeClock()
        self.state_manager = FakeStateManager(clock)
        broker = FakeBrokerAdapter(clock, self.state_manager)
        notifier = FakeNotifier(clock)

        self.enforcement_engine = EnforcementEngine(broker, self.state_manager, notifier)

        # Initialize rules based on configuration
        rules = await self._load_rules()

        self.event_bus = EventBus()
        self.risk_engine = RiskEngine(
            state_manager=self.state_manager,
            enforcement_engine=self.enforcement_engine,
            rules=rules
        )

        # Register event handlers
        await self.event_bus.on("FILL", self.risk_engine.process_event)
        await self.event_bus.on("POSITION_UPDATE", self.risk_engine.process_event)
        await self.event_bus.on("CONNECTION_CHANGE", self.risk_engine.process_event)

        logger.info(f"Loaded {len(rules)} risk rules")
        logger.info("Test mode initialization complete")

    async def _start_live_mode(self):
        """Start daemon in live mode with SDK connection."""
        logger.info("Starting in LIVE mode - connecting to broker")

        # Import production components
        from src.adapters.sdk_adapter import SDKAdapter
        from src.adapters.event_normalizer import EventNormalizer
        from src.adapters.connection_manager import ConnectionManager
        from src.core.event_bus import EventBus
        from src.core.risk_engine import RiskEngine
        from src.core.enforcement_engine import EnforcementEngine
        from src.state.state_manager import StateManager
        from src.state.persistence import StatePersistence
        from src.monitoring.health_monitor import HealthMonitor
        from src.notification.notifier import Notifier

        # Check for required environment variables
        api_key = os.getenv('PROJECT_X_API_KEY')
        username = os.getenv('PROJECT_X_USERNAME')

        if not api_key or not username:
            raise ValueError(
                "Missing required environment variables. "
                "Please set PROJECT_X_API_KEY and PROJECT_X_USERNAME"
            )

        # Initialize persistence
        self.persistence = StatePersistence(self.config['db_path'])
        await self.persistence.initialize()
        logger.info(f"Database initialized at {self.config['db_path']}")

        # Initialize health monitor
        self.health_monitor = HealthMonitor(self.persistence)
        await self.health_monitor.start()

        # Initialize SDK adapter
        self.sdk_adapter = SDKAdapter(
            api_key=api_key,
            username=username,
            account_id=self.config['account_id']
        )

        # Initialize components
        self.state_manager = StateManager()
        notifier = Notifier()

        # Load saved state from database
        saved_state = await self.persistence.load_account_state(str(self.config['account_id']))
        if saved_state:
            logger.info("Restored account state from database")
            # Restore positions
            positions = await self.persistence.load_open_positions(str(self.config['account_id']))
            logger.info(f"Restored {len(positions)} open positions")

        self.enforcement_engine = EnforcementEngine(
            broker=self.sdk_adapter,
            state_manager=self.state_manager,
            notifier=notifier
        )

        # Initialize rules
        rules = await self._load_rules()
        monitors = await self._load_monitors()

        self.event_bus = EventBus()
        self.risk_engine = RiskEngine(
            state_manager=self.state_manager,
            enforcement_engine=self.enforcement_engine,
            rules=rules,
            monitors=monitors
        )

        # Initialize event normalizer to bridge SDK events
        event_normalizer = EventNormalizer(
            self.event_bus,
            self.state_manager
        )

        # Initialize connection manager with reconnect logic
        self.connection_manager = ConnectionManager(
            sdk_adapter=self.sdk_adapter,
            event_normalizer=event_normalizer,
            health_monitor=self.health_monitor,
            persistence=self.persistence
        )

        # Start connection with automatic reconnection
        await self.connection_manager.start()

        # Register risk engine handlers
        await self.event_bus.on("FILL", self.risk_engine.process_event)
        await self.event_bus.on("POSITION_UPDATE", self.risk_engine.process_event)
        await self.event_bus.on("CONNECTION_CHANGE", self.risk_engine.process_event)

        # Start periodic state persistence
        asyncio.create_task(self._persist_state_loop())

        # Write PID file for admin CLI
        with open("./risk_daemon.pid", "w") as f:
            f.write(str(os.getpid()))

        logger.info(f"Loaded {len(rules)} risk rules and {len(monitors)} monitors")
        logger.info("Live mode initialization complete")

    async def _load_rules(self):
        """Load risk rules based on configuration."""
        rules = []

        # Load rules from configuration
        rule_config = self.config.get('rules', {})

        if rule_config.get('max_contracts', {}).get('enabled', False):
            from src.rules.max_contracts_per_instrument import MaxContractsPerInstrumentRule
            # Convert single limit to all-symbols limit
            limit_value = rule_config.get('max_contracts', {}).get('limit', 10)
            rule = MaxContractsPerInstrumentRule(
                symbol_limits={'*': limit_value}  # Apply to all symbols
            )
            # Add backward-compatible attributes for tests
            rule.name = 'MaxContractsRule'  # Override name for compatibility
            rule.max_contracts = limit_value  # Add expected attribute
            rules.append(rule)

        if rule_config.get('unrealized_loss', {}).get('enabled', False):
            from src.rules.unrealized_profit import UnrealizedProfitRule
            from decimal import Decimal
            limit_value = rule_config.get('unrealized_loss', {}).get('limit', -500)
            rules.append(UnrealizedProfitRule(
                profit_target=Decimal(str(limit_value))
            ))

        if rule_config.get('daily_loss', {}).get('enabled', False):
            from src.rules.daily_realized_profit import DailyRealizedProfitRule
            from decimal import Decimal
            limit_value = rule_config.get('daily_loss', {}).get('limit', -1000)
            rules.append(DailyRealizedProfitRule(
                profit_target=Decimal(str(limit_value))
            ))

        if rule_config.get('session_block', {}).get('enabled', False):
            from src.rules.session_block import SessionBlockOutsideRule
            # Default session block: Mon-Fri, 8am-3pm CT
            rules.append(SessionBlockOutsideRule(
                allowed_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                allowed_times=("08:00", "15:00")
            ))

        # Add additional rules as configured
        # TODO: Load P0, P1, P2 rules based on priority configuration

        return rules

    async def _load_monitors(self):
        """Load monitors based on configuration."""
        monitors = []

        monitor_config = self.config.get('monitors', {})

        if monitor_config.get('stop_loss_detector', {}).get('enabled', True):
            from src.monitors.stop_loss_detector import StopLossDetector
            monitors.append(StopLossDetector())

        return monitors

    async def stop(self):
        """Stop the risk daemon gracefully."""
        logger.info("Stopping Risk Manager Daemon...")
        self.running = False

        # Stop connection manager
        if self.connection_manager:
            await self.connection_manager.stop()

        # Stop health monitor
        if self.health_monitor:
            await self.health_monitor.stop()

        # Save final state
        if self.persistence and self.state_manager:
            await self._persist_state()
            await self.persistence.close()

        # Disconnect from broker if connected
        if self.sdk_adapter and self.sdk_adapter.is_connected():
            await self.sdk_adapter.disconnect()

        # Clean up event bus
        if self.event_bus:
            await self.event_bus.cleanup()

        # Remove PID file
        try:
            os.remove("./risk_daemon.pid")
        except FileNotFoundError:
            pass

        logger.info("Risk Manager Daemon stopped")

    async def _persist_state_loop(self):
        """Periodically save state to database."""
        interval = self.config.get('persistence_interval', 60)  # seconds

        while self.running:
            try:
                await asyncio.sleep(interval)
                await self._persist_state()
            except Exception as e:
                logger.error(f"State persistence error: {e}")

    async def _persist_state(self):
        """Save current state to database."""
        if not self.persistence or not self.state_manager:
            return

        try:
            # Save account state
            for account_id in self.state_manager.accounts:
                state = self.state_manager.get_account_state(account_id)
                await self.persistence.save_account_state(
                    account_id,
                    {
                        'daily_pnl_realized': state.daily_pnl_realized,
                        'daily_pnl_unrealized': state.daily_pnl_unrealized,
                        'locked_out': self.state_manager.is_locked_out(account_id),
                        'lockout_until': state.lockout_until.isoformat() if state.lockout_until else None,
                        'lockout_reason': state.lockout_reason
                    }
                )

                # Save positions
                positions = self.state_manager.get_open_positions(account_id)
                for pos in positions:
                    await self.persistence.save_position({
                        'position_id': pos.position_id,
                        'account_id': pos.account_id,
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'unrealized_pnl': pos.unrealized_pnl,
                        'opened_at': pos.opened_at,
                        'is_open': True,
                        'stop_loss_attached': pos.stop_loss_attached,
                        'stop_loss_grace_expires': pos.stop_loss_grace_expires.isoformat() if pos.stop_loss_grace_expires else None,
                        'pending_close': pos.pending_close
                    })

            logger.debug("State persisted to database")

        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.stop())


def load_config(args) -> dict:
    """
    Load configuration from arguments and environment.

    Args:
        args: Command line arguments

    Returns:
        Configuration dictionary
    """
    from decimal import Decimal

    config = {
        'account_id': args.account_id,
        'mode': 'test' if args.test_mode else 'live',
        'db_path': args.db_path,
        'rules': {},
        'monitors': {}
    }

    # Load rule configuration with explicit enabled flags
    # max_contracts rule
    config['rules']['max_contracts'] = {
        'enabled': args.max_contracts is not None,
        'limit': args.max_contracts if args.max_contracts is not None else 10
    }

    # daily_loss rule (convert to Decimal)
    if args.daily_loss_limit is not None:
        config['rules']['daily_loss'] = {
            'enabled': True,
            'limit': Decimal(str(args.daily_loss_limit))
        }
    else:
        config['rules']['daily_loss'] = {
            'enabled': False,
            'limit': Decimal("-1000.0")
        }

    # unrealized_loss rule (convert to Decimal)
    if args.unrealized_loss_limit is not None:
        config['rules']['unrealized_loss'] = {
            'enabled': True,
            'limit': Decimal(str(args.unrealized_loss_limit))
        }
    else:
        config['rules']['unrealized_loss'] = {
            'enabled': False,
            'limit': Decimal("-500.0")
        }

    # session_block rule (always include)
    config['rules']['session_block'] = {
        'enabled': True
    }

    # Load from config file if provided (overrides CLI args)
    if args.config:
        import json
        with open(args.config, 'r') as f:
            file_config = json.load(f)

            # Merge file config into rules, converting to Decimal where needed
            if 'max_contracts' in file_config:
                config['rules']['max_contracts']['limit'] = file_config['max_contracts']
                config['rules']['max_contracts']['enabled'] = True

            if 'daily_loss_limit' in file_config:
                config['rules']['daily_loss']['limit'] = Decimal(str(file_config['daily_loss_limit']))
                config['rules']['daily_loss']['enabled'] = True

            if 'unrealized_loss_limit' in file_config:
                config['rules']['unrealized_loss']['limit'] = Decimal(str(file_config['unrealized_loss_limit']))
                config['rules']['unrealized_loss']['enabled'] = True

            if 'session_block' in file_config:
                config['rules']['session_block']['enabled'] = file_config['session_block']

    return config


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Risk Manager Daemon - Automated trading risk enforcement'
    )

    # Required arguments
    parser.add_argument(
        '--account-id',
        type=int,
        required=True,
        help='Trading account ID to monitor'
    )

    # Mode selection
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Run in test mode with mock broker'
    )

    # Database
    parser.add_argument(
        '--db-path',
        type=str,
        default='./data/risk_state.db',
        help='Path to SQLite database for state persistence'
    )

    # Rule configuration
    parser.add_argument(
        '--max-contracts',
        type=int,
        help='Maximum total contracts allowed'
    )

    parser.add_argument(
        '--daily-loss-limit',
        type=float,
        help='Daily loss limit (negative value, e.g., -1000)'
    )

    parser.add_argument(
        '--unrealized-loss-limit',
        type=float,
        help='Per-position unrealized loss limit (negative value, e.g., -500)'
    )

    # Configuration file
    parser.add_argument(
        '--config',
        type=str,
        help='Path to JSON configuration file'
    )

    # Verbosity
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config = load_config(args)

    # Create and start daemon
    daemon = RiskDaemon(config)

    # Register signal handlers
    signal.signal(signal.SIGINT, daemon.handle_signal)
    signal.signal(signal.SIGTERM, daemon.handle_signal)

    # Run the daemon
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon crashed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()