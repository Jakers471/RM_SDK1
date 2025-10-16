# Extensibility and Future Features

## Overview

The Risk Manager Daemon is designed with extensibility as a core principle. While the initial version includes 12 risk rules and core functionality, the system must easily accommodate future enhancements like auto-breakeven, trailing stops, advanced analytics, and more. This document outlines the plugin architecture and extension patterns that make the system future-proof.

## Extensibility Principles

### 1. Plugin-Based Rule System

**Design**: Each risk rule is a self-contained plugin that implements a standard interface.

**Benefits**:
- **Add new rules** without modifying core engine
- **Enable/disable rules** independently
- **Test rules** in isolation
- **Share rules** across projects (if open-sourced)

**Plugin Interface**:
```python
class RiskRulePlugin:
    # Metadata
    name: str              # e.g., "MaxContracts"
    version: str           # e.g., "1.0.0"
    description: str       # Human-readable description
    author: str            # Plugin author

    # Configuration
    config_schema: dict    # JSON schema for rule parameters

    # Lifecycle
    def __init__(self, params: dict):
        # Initialize with configured parameters
        pass

    def applies_to_event(self, event_type: str) -> bool:
        # Does this rule care about this event?
        return event_type in ["fill", "position_update"]

    def evaluate(self, event: Event, state: AccountState) -> Optional[RuleViolation]:
        # Evaluate rule against event and state
        # Return violation if breached, None if OK
        pass

    def get_enforcement_action(self, violation: RuleViolation) -> EnforcementAction:
        # Determine what action to take
        pass
```

**Example: Auto-Breakeven Plugin** (future feature):
```python
class AutoBreakevenRule(RiskRulePlugin):
    name = "AutoBreakeven"
    version = "1.0.0"
    description = "Moves stop loss to breakeven when profit target reached"

    config_schema = {
        "profit_trigger": {"type": "float", "description": "Unrealized profit to trigger breakeven"},
        "enabled": {"type": "bool"}
    }

    def __init__(self, params):
        self.profit_trigger = params["profit_trigger"]

    def applies_to_event(self, event_type):
        return event_type == "position_update"

    def evaluate(self, event, state):
        position = state.get_position(event.symbol)

        if position.unrealized_pnl >= self.profit_trigger:
            if position.stop_loss != position.entry_price:
                return RuleViolation(
                    rule=self.name,
                    message=f"Position at +${position.unrealized_pnl}, moving stop to breakeven",
                    severity="info"
                )

        return None

    def get_enforcement_action(self, violation):
        return EnforcementAction(
            type="modify_stop_loss",
            position_id=violation.position_id,
            new_stop_price=violation.position.entry_price,
            reason="Auto-breakeven triggered"
        )
```

### 2. Modular Component Design

**Core Components** are independent and swappable:

- **SDK Adapter**: Abstract broker-specific code
- **Event Bus**: Standard pub/sub pattern
- **State Manager**: Clean query interface
- **Enforcement Engine**: Reusable action executor
- **Notification Service**: Support multiple channels

**Adding New Component** (e.g., Analytics Module):

```python
class AnalyticsModule:
    def __init__(self, state_manager):
        self.state_manager = state_manager

    def on_enforcement_action(self, action):
        # Track enforcement metrics
        self.track_rule_violation(action.rule, action.account_id)

    def get_daily_stats(self, account_id):
        # Return analytics: win rate, avg loss, enforcement frequency, etc.
        pass
```

Register with event bus:
```python
event_bus.subscribe("enforcement_action", analytics_module.on_enforcement_action)
```

### 3. Configuration Schema Versioning

**Version Field** in all config files:
```json
{
  "version": "1.2",
  "rules": [...]
}
```

**Migration Scripts** handle version upgrades:
```python
def migrate_config_1_0_to_1_1(old_config):
    # Add new fields with defaults
    for rule in old_config["rules"]:
        if rule["name"] == "NewRule":
            # This rule didn't exist in 1.0
            continue

    # Add new rule with default params
    old_config["rules"].append({
        "name": "AutoBreakeven",
        "enabled": False,
        "params": {"profit_trigger": 100.0}
    })

    old_config["version"] = "1.1"
    return old_config
```

### 4. Event-Driven Extensions

**Custom Event Types** can be added without breaking existing code:

```python
# Core events
EventType = Literal["fill", "position_update", "order_update", "position_close", "connection_status"]

# Future extension
EventType = Literal[..., "trade_signal", "market_data_update", "news_event"]
```

New rules can listen for new event types. Old rules ignore events they don't care about.

### 5. API-First Design

**Internal APIs** between components are well-defined:

```python
# State Manager API
state_manager.get_positions(account_id)
state_manager.get_pnl(account_id)
state_manager.is_locked_out(account_id)

# Enforcement Engine API
enforcement_engine.close_position(account_id, position_id, reason)
enforcement_engine.flatten_account(account_id, reason)

# Notification Service API
notification_service.send_alert(account_id, message, severity)
```

**Future External API** (if needed):
- REST API for external integrations
- Webhooks to send events to external systems
- Query API for third-party analytics tools

---

## Future Features Roadmap

### Phase 1 (Current): Core Risk Management
- 12 risk rules
- Event-driven enforcement
- Admin/Trader CLIs
- Notifications and logging

### Phase 2: Advanced Automation
**Auto-Breakeven**:
- Move stop to breakeven after profit target
- Configurable trigger and offset

**Trailing Stops**:
- Automatically adjust stop loss as profit increases
- Configurable trail distance

**Position Scaling**:
- Auto-scale into positions (add contracts at certain price levels)
- Auto-scale out (take partial profits)

**Smart Order Management**:
- Bracket orders (entry + stop + target as package)
- OCO orders (one-cancels-other)

### Phase 3: Analytics and Reporting
**Performance Analytics**:
- Win rate, avg win/loss, profit factor
- Rule enforcement frequency (which rules trigger most)
- Best/worst trading hours
- Per-instrument performance

**Dashboard**:
- Web-based dashboard (read-only for trader, full control for admin)
- Real-time charts (PnL over time, position exposure)
- Historical data visualization

**Reporting**:
- Daily/weekly/monthly reports (email or PDF)
- Compliance reports (for funded account programs)
- Trade journal integration

### Phase 4: Multi-Broker Support
**Abstract Broker Interface**:
- Support brokers beyond TopstepX (NinjaTrader, TD Ameritrade, Interactive Brokers)
- Common SDK adapter interface
- Broker-specific plugins

### Phase 5: Advanced Features
**Machine Learning Integration**:
- Detect trading patterns (revenge trading, overtrading)
- Adaptive limits (tighten rules during losing streaks)
- Anomaly detection (unusual trading behavior)

**Strategy Integration**:
- Define allowed strategies (only trade certain setups)
- Strategy-specific rules (different limits per strategy)

**Multi-Account Aggregation**:
- Track combined PnL across all accounts
- Aggregate limits (total daily loss across all accounts)

**Cloud Deployment**:
- Run daemon on VPS (24/7 monitoring even if PC off)
- Remote access to CLI via web

---

## How to Add New Features

### Adding a New Risk Rule

**Steps**:

1. **Create Rule Plugin**:
   ```python
   # src/rules/my_new_rule.py
   class MyNewRule(RiskRulePlugin):
       name = "MyNewRule"
       # Implement interface
   ```

2. **Define Config Schema**:
   ```python
   config_schema = {
       "param1": {"type": "float", "description": "..."},
       "param2": {"type": "int", "description": "..."}
   }
   ```

3. **Register Rule**:
   ```python
   # src/risk_engine.py
   from rules.my_new_rule import MyNewRule

   available_rules["MyNewRule"] = MyNewRule
   ```

4. **Add to Config**:
   ```json
   // risk_rules.json
   {
     "rule": "MyNewRule",
     "enabled": true,
     "params": {
       "param1": 100.0,
       "param2": 5
     }
   }
   ```

5. **Test Independently**:
   ```python
   # tests/test_my_new_rule.py
   def test_my_new_rule():
       rule = MyNewRule({"param1": 100.0, "param2": 5})
       violation = rule.evaluate(mock_event, mock_state)
       assert violation is not None
   ```

**No changes to core engine needed!**

### Adding a New Enforcement Action Type

**Example**: Modify stop loss (for auto-breakeven)

1. **Define Action Type**:
   ```python
   class EnforcementAction:
       type: Literal["close_position", "flatten_account", "set_lockout", "start_cooldown", "send_alert", "modify_stop_loss"]
   ```

2. **Implement in Enforcement Engine**:
   ```python
   def modify_stop_loss(self, account_id, position_id, new_stop_price, reason):
       # Send order modification via SDK Adapter
       sdk_adapter.modify_order(account_id, position_id, stop_price=new_stop_price)
       logger.log_enforcement(f"Modified stop loss: {reason}")
   ```

3. **Add to Enforcement Engine Handler**:
   ```python
   def execute(self, action):
       if action.type == "modify_stop_loss":
           self.modify_stop_loss(action.account_id, action.position_id, action.new_stop_price, action.reason)
   ```

### Adding a New Notification Channel

**Example**: Email notifications

1. **Create Email Notification Handler**:
   ```python
   # src/notifications/email_notifier.py
   class EmailNotifier:
       def __init__(self, smtp_config):
           self.smtp_config = smtp_config

       def send(self, to, subject, message):
           # Send email via SMTP
   ```

2. **Register with Notification Service**:
   ```python
   # src/notification_service.py
   if config.notifications.email.enabled:
       email_notifier = EmailNotifier(config.notifications.email)
       self.channels["email"] = email_notifier
   ```

3. **Add to Config**:
   ```json
   {
     "email": {
       "enabled": true,
       "smtp_server": "smtp.gmail.com",
       "smtp_port": 587,
       "from_address": "risk-manager@example.com",
       "to_address": "trader@example.com"
     }
   }
   ```

### Adding a New CLI Menu

**Example**: Analytics menu in Trader CLI

1. **Create Menu Handler**:
   ```python
   def show_analytics_menu(account_id):
       print("=== ANALYTICS ===")
       stats = analytics_module.get_daily_stats(account_id)
       print(f"Trades Today: {stats.trade_count}")
       print(f"Win Rate: {stats.win_rate}%")
       # ...
   ```

2. **Add to Main Menu**:
   ```python
   trader_menu = [
       "1. Dashboard",
       "2. View Positions",
       "3. Analytics",  # NEW
       # ...
   ]

   if choice == "3":
       show_analytics_menu(account_id)
   ```

---

## Plugin Discovery and Loading

### Auto-Discovery (Future Enhancement)

Plugins can be auto-discovered from directory:

```
src/
  rules/
    __init__.py
    max_contracts.py
    unrealized_loss.py
    auto_breakeven.py  # NEW PLUGIN
```

```python
# Auto-load all plugins
import importlib
import os

rules_dir = "src/rules"
for file in os.listdir(rules_dir):
    if file.endswith(".py") and file != "__init__.py":
        module = importlib.import_module(f"rules.{file[:-3]}")
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, RiskRulePlugin):
                available_rules[obj.name] = obj
```

This allows dropping new rule files into `rules/` directory and they're automatically loaded.

---

## Backward Compatibility

### Config Compatibility

When adding new features:
- **Old configs must still work** (don't break existing setups)
- **New fields have defaults** (optional, not required)
- **Migration scripts** handle version upgrades

### API Compatibility

When changing internal APIs:
- **Deprecate old methods** before removing (give warning)
- **Maintain old interface** for at least one major version
- **Document breaking changes** clearly

### State Compatibility

When changing state schema:
- **Migrate old state files** on load
- **Keep state version field** for detection
- **Test migration paths** thoroughly

---

## Third-Party Integrations

### Webhook Support (Future)

Allow external systems to react to events:

```json
{
  "webhooks": {
    "on_enforcement": "https://example.com/api/enforcement",
    "on_lockout": "https://example.com/api/lockout"
  }
}
```

Daemon sends HTTP POST to webhook URL when event occurs.

### External Data Sources (Future)

Allow rules to use external data:

```python
class NewsBasedRule(RiskRulePlugin):
    def evaluate(self, event, state):
        # Query external news API
        news = fetch_news(event.symbol)

        if news.sentiment == "extremely_negative":
            return RuleViolation(
                message="High-impact negative news, blocking trades"
            )
```

### Trade Journal Integration (Future)

Export trades to third-party journals:

```python
class TradeJournalExporter:
    def on_position_close(self, position, realized_pnl):
        # Export to Tradervue, Edgewonk, etc.
        journal_api.create_trade({
            "symbol": position.symbol,
            "entry_price": position.entry_price,
            "exit_price": position.exit_price,
            "pnl": realized_pnl
        })
```

---

## Testing Extensions

### Plugin Testing Framework

Provide test utilities for plugin developers:

```python
from risk_manager.testing import RuleTester

def test_my_rule():
    tester = RuleTester(MyNewRule, params={"threshold": 100})

    # Simulate fill event
    result = tester.send_event("fill", {
        "symbol": "MNQ",
        "quantity": 2,
        "price": 5000
    })

    assert result.violation is None  # Rule not violated

    # Simulate position update
    result = tester.send_event("position_update", {
        "symbol": "MNQ",
        "unrealized_pnl": -150
    })

    assert result.violation is not None  # Rule violated
    assert result.enforcement_action.type == "close_position"
```

---

## Documentation for Extensions

### Plugin Development Guide

Provide documentation:
- **Plugin Interface Reference**: Complete API docs
- **Example Plugins**: Well-commented examples
- **Best Practices**: Dos and don'ts
- **Testing Guide**: How to test plugins
- **Contribution Guide**: How to share plugins with community

### Extension Registry

Maintain registry of available plugins:
- Official plugins (built-in)
- Community plugins (third-party)
- Plugin ratings and reviews (if open-source)

---

## Performance Considerations for Extensions

### Plugin Overhead

Each plugin adds processing overhead:
- **Lazy loading**: Only load enabled plugins
- **Event filtering**: Plugins declare which events they care about
- **Caching**: Plugins can cache results if expensive

### Resource Limits

Prevent poorly-written plugins from consuming resources:
- **Timeout**: Plugin evaluation must complete within X ms (e.g., 100ms)
- **Memory limit**: Plugins limited in memory usage
- **Error isolation**: Plugin crash doesn't crash daemon

---

## Summary for Implementation Agent

**To implement extensibility, you need to:**

1. **Define RiskRulePlugin interface** clearly
2. **Make core components modular** (event bus, state manager, etc.)
3. **Create plugin registration system**
4. **Build config schema versioning** and migrations
5. **Design API interfaces** between components
6. **Document extension patterns** for future developers
7. **Create example plugins** (e.g., simple rule)
8. **Build plugin testing framework**
9. **Ensure backward compatibility** for config and state
10. **Plan for future features** (auto-breakeven, trailing stops, analytics)

Extensibility is what turns this from a **one-time tool** into a **long-term platform**. By designing for plugins and modularity from day one, we enable continuous improvement without major refactoring. The user mentioned they'll add features like auto-breakeven later - the architecture must make this **easy**, not painful.
