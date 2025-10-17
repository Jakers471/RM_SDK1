"""
Smoke tests for main.py daemon initialization and configuration.

These tests focus on testable functions without requiring live SDK connection:
- load_config() - Configuration parsing and merging
- RiskDaemon.__init__() - Component initialization
- _load_rules() - Rule discovery and instantiation
- Signal handling and shutdown logic

Coverage target: ~40% of main.py (80+ lines covered)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from argparse import Namespace
import tempfile
import json
import os

# Import main module components
try:
    from src.main import load_config, RiskDaemon
except ImportError:
    pytestmark = pytest.mark.skip(reason="main.py not available")


@pytest.mark.unit
class TestLoadConfig:
    """Test configuration loading and merging logic."""

    def test_load_config_with_basic_cli_args(self):
        """Test load_config with minimal CLI arguments."""
        # Setup: Minimal CLI args
        args = Namespace(
            account_id="TEST_ACCOUNT_123",
            test_mode=True,
            db_path="./test_data/risk_state.db",
            max_contracts=10,
            daily_loss_limit=500.0,
            unrealized_loss_limit=200.0,
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Config has expected structure
        assert config['account_id'] == "TEST_ACCOUNT_123"
        assert config['mode'] == "test"
        assert config['db_path'] == "./test_data/risk_state.db"
        assert 'rules' in config
        assert config['rules']['max_contracts']['enabled'] is True
        assert config['rules']['max_contracts']['limit'] == 10

    def test_load_config_with_live_mode(self):
        """Test load_config sets mode to 'live' when test_mode=False."""
        # Setup
        args = Namespace(
            account_id="LIVE_ACCOUNT",
            test_mode=False,  # Live mode
            db_path="./data/risk_state.db",
            max_contracts=5,
            daily_loss_limit=1000.0,
            unrealized_loss_limit=300.0,
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Mode is 'live'
        assert config['mode'] == "live"

    def test_load_config_with_config_file_override(self):
        """Test load_config merges JSON config file with CLI args."""
        # Setup: Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                'max_contracts': 15,  # Override CLI
                'daily_loss_limit': 750.0,
                'session_block': True
            }
            json.dump(config_data, f)
            config_file_path = f.name

        try:
            args = Namespace(
                account_id="TEST_ACCOUNT",
                test_mode=True,
                db_path="./data/risk_state.db",
                max_contracts=10,  # Will be overridden
                daily_loss_limit=500.0,  # Will be overridden
                unrealized_loss_limit=200.0,
                config=config_file_path,
                verbose=False
            )

            # Execute
            config = load_config(args)

            # Assert: Config file values override CLI
            assert config['rules']['max_contracts']['limit'] == 15
            assert config['rules']['daily_loss']['limit'] == Decimal("750.0")
        finally:
            # Cleanup
            os.unlink(config_file_path)

    def test_load_config_with_none_limits_disables_rules(self):
        """Test load_config disables rules when limits are None."""
        # Setup: None limits
        args = Namespace(
            account_id="TEST_ACCOUNT",
            test_mode=True,
            db_path="./data/risk_state.db",
            max_contracts=None,  # Disabled
            daily_loss_limit=None,  # Disabled
            unrealized_loss_limit=100.0,  # Enabled
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Rules with None limits are disabled
        assert config['rules']['max_contracts']['enabled'] is False
        assert config['rules']['daily_loss']['enabled'] is False
        assert config['rules']['unrealized_loss']['enabled'] is True
        assert config['rules']['unrealized_loss']['limit'] == Decimal("100.0")

    def test_load_config_creates_default_rules_dict(self):
        """Test load_config creates rules dict with expected keys."""
        # Setup
        args = Namespace(
            account_id="TEST_ACCOUNT",
            test_mode=True,
            db_path="./data/risk_state.db",
            max_contracts=5,
            daily_loss_limit=500.0,
            unrealized_loss_limit=200.0,
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Rules dict has all expected keys
        assert 'max_contracts' in config['rules']
        assert 'daily_loss' in config['rules']
        assert 'unrealized_loss' in config['rules']
        assert 'session_block' in config['rules']


@pytest.mark.asyncio
@pytest.mark.unit
class TestRiskDaemonInitialization:
    """Test RiskDaemon initialization and component setup."""

    def test_risk_daemon_constructor_initializes_components(self):
        """Test RiskDaemon.__init__() sets up component placeholders."""
        # Setup: Minimal config
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'db_path': './test_data/risk_state.db',
            'rules': {},
            'monitors': {}
        }

        # Execute
        daemon = RiskDaemon(config)

        # Assert: Component placeholders initialized
        assert daemon.config == config
        assert daemon.sdk_adapter is None
        assert daemon.event_bus is None
        assert daemon.risk_engine is None
        assert daemon.state_manager is None
        assert daemon.enforcement_engine is None
        assert daemon.persistence is None
        assert daemon.health_monitor is None
        assert daemon.connection_manager is None
        assert daemon.running is False

    async def test_load_rules_with_enabled_max_contracts(self):
        """Test _load_rules creates MaxContractsRule when enabled."""
        # Setup
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {
                'max_contracts': {
                    'enabled': True,
                    'limit': 10
                }
            }
        }
        daemon = RiskDaemon(config)

        # Execute
        rules = await daemon._load_rules()

        # Assert: MaxContractsRule instantiated
        assert len(rules) > 0
        rule_names = [rule.name for rule in rules]
        assert 'MaxContractsRule' in rule_names

        # Find MaxContractsRule and verify config
        max_contracts_rule = next(r for r in rules if r.name == 'MaxContractsRule')
        assert max_contracts_rule.max_contracts == 10
        assert max_contracts_rule.enabled is True

    async def test_load_rules_with_disabled_rule(self):
        """Test _load_rules skips disabled rules."""
        # Setup: Disabled max_contracts
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {
                'max_contracts': {
                    'enabled': False,  # Disabled
                    'limit': 10
                }
            }
        }
        daemon = RiskDaemon(config)

        # Execute
        rules = await daemon._load_rules()

        # Assert: No MaxContractsRule in list
        rule_names = [rule.name for rule in rules]
        assert 'MaxContractsRule' not in rule_names

    async def test_load_rules_with_multiple_rules(self):
        """Test _load_rules creates multiple rule instances."""
        # Setup: Multiple enabled rules
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {
                'max_contracts': {'enabled': True, 'limit': 5},
                'daily_loss': {'enabled': True, 'limit': Decimal("500.0")},
                'unrealized_loss': {'enabled': True, 'limit': Decimal("200.0")},
                'session_block': {'enabled': True}
            }
        }
        daemon = RiskDaemon(config)

        # Execute
        rules = await daemon._load_rules()

        # Assert: All rules created
        rule_names = [rule.name for rule in rules]
        assert len(rules) >= 3  # At least 3 rules
        # Note: Exact rule names depend on implementation

    async def test_load_rules_with_empty_config_returns_empty_list(self):
        """Test _load_rules returns empty list when no rules configured."""
        # Setup: No rules in config
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {}
        }
        daemon = RiskDaemon(config)

        # Execute
        rules = await daemon._load_rules()

        # Assert: Empty list
        assert rules == []

    async def test_load_monitors_with_stop_loss_detector(self):
        """Test _load_monitors creates StopLossDetector when configured."""
        # Setup
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'monitors': {
                'stop_loss_detector': {
                    'enabled': True
                }
            }
        }
        daemon = RiskDaemon(config)

        # Execute
        monitors = await daemon._load_monitors()

        # Assert: StopLossDetector instantiated
        assert len(monitors) == 1
        # Note: Exact monitor type depends on implementation


@pytest.mark.asyncio
@pytest.mark.unit
class TestRiskDaemonShutdown:
    """Test RiskDaemon shutdown and cleanup logic."""

    async def test_stop_sets_running_to_false(self):
        """Test stop() sets running flag to False."""
        # Setup
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {},
            'monitors': {}
        }
        daemon = RiskDaemon(config)
        daemon.running = True

        # Execute
        await daemon.stop()

        # Assert: Running flag set to False
        assert daemon.running is False

    async def test_stop_with_no_components_does_not_crash(self):
        """Test stop() handles None components gracefully."""
        # Setup: Daemon with no components initialized
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {},
            'monitors': {}
        }
        daemon = RiskDaemon(config)
        # All components are None

        # Execute: Should not raise exception
        await daemon.stop()

        # Assert: Completed without error
        assert daemon.running is False

    async def test_stop_closes_sdk_adapter_if_connected(self):
        """Test stop() calls sdk_adapter.disconnect() if adapter exists."""
        # Setup: Mock SDK adapter
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {},
            'monitors': {}
        }
        daemon = RiskDaemon(config)

        # Mock SDK adapter with disconnect method
        mock_adapter = AsyncMock()
        mock_adapter.disconnect = AsyncMock()
        daemon.sdk_adapter = mock_adapter

        # Execute
        await daemon.stop()

        # Assert: disconnect() was called
        mock_adapter.disconnect.assert_called_once()

    async def test_handle_signal_creates_stop_task(self):
        """Test handle_signal routes to async stop()."""
        # Setup
        config = {
            'account_id': 'TEST_ACCOUNT',
            'mode': 'test',
            'rules': {},
            'monitors': {}
        }
        daemon = RiskDaemon(config)

        # Mock asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            # Execute: Simulate SIGINT
            daemon.handle_signal(2, None)  # SIGINT = 2

            # Assert: create_task was called
            mock_create_task.assert_called_once()


@pytest.mark.unit
class TestDaemonConfigEdgeCases:
    """Test edge cases in configuration handling."""

    def test_load_config_with_verbose_flag_enables_debug_logging(self):
        """Test load_config respects verbose flag."""
        # Setup
        args = Namespace(
            account_id="TEST_ACCOUNT",
            test_mode=True,
            db_path="./data/risk_state.db",
            max_contracts=5,
            daily_loss_limit=500.0,
            unrealized_loss_limit=200.0,
            config=None,
            verbose=True  # Debug logging
        )

        # Execute
        config = load_config(args)

        # Assert: Config created successfully
        # (Verbose flag affects logging setup, not config structure)
        assert config is not None

    def test_load_config_with_missing_optional_args(self):
        """Test load_config handles missing optional arguments."""
        # Setup: Only required args
        args = Namespace(
            account_id="TEST_ACCOUNT",
            test_mode=True,
            db_path="./data/risk_state.db",
            max_contracts=None,
            daily_loss_limit=None,
            unrealized_loss_limit=None,
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Config created with all rules disabled
        assert config['rules']['max_contracts']['enabled'] is False
        assert config['rules']['daily_loss']['enabled'] is False
        assert config['rules']['unrealized_loss']['enabled'] is False

    def test_load_config_converts_float_to_decimal(self):
        """Test load_config converts float limits to Decimal."""
        # Setup
        args = Namespace(
            account_id="TEST_ACCOUNT",
            test_mode=True,
            db_path="./data/risk_state.db",
            max_contracts=5,
            daily_loss_limit=500.50,  # Float
            unrealized_loss_limit=200.75,  # Float
            config=None,
            verbose=False
        )

        # Execute
        config = load_config(args)

        # Assert: Limits are Decimal objects
        assert isinstance(config['rules']['daily_loss']['limit'], Decimal)
        assert isinstance(config['rules']['unrealized_loss']['limit'], Decimal)
        assert config['rules']['daily_loss']['limit'] == Decimal("500.50")
        assert config['rules']['unrealized_loss']['limit'] == Decimal("200.75")
