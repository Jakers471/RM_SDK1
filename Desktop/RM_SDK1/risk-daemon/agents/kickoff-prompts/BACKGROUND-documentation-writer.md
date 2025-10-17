# BACKGROUND RESEARCH: Documentation Writer Kickoff

**Agent**: documentation-writer
**Model**: opus
**Priority**: Background (PARALLEL with Phase 1)
**Estimated Time**: 2-3 hours
**Status**: Ready to run

---

## 📖 FIRST: Read Your Agent Definition

**CRITICAL**: Before starting, read your complete agent definition:
```
agents/background-research/documentation-writer.md
```

This file contains your full mission, constraints, and quality standards. The kickoff below is a quick-start summary.

---

## 🎯 Your Mission

You are the **documentation-writer** agent. Create comprehensive user-facing documentation for traders and admins. Write for non-technical traders and technical admins.

## 📚 Required Reading

1. **docs/architecture/** (What the system does)
   - Understand: Risk rules, enforcement actions, daemon lifecycle
   - Extract: Features to document

2. **src/** (How it works)
   - Review: CLI commands, config structure, notifications
   - Understand: User-facing functionality

3. **docs/audits/** (What's being built)
   - Extract: Missing components being added in Phase 1

## 📝 Your Deliverables

### 1. docs/user-guides/installation_guide.md

**For: Admins (Technical)**

```markdown
# Risk Daemon Installation Guide

## System Requirements
- Windows 10/11
- Python 3.11+
- Administrative privileges
- 500MB disk space
- 512MB RAM minimum

## Installation Steps

### 1. Install Python
[Step-by-step with screenshots if possible]

### 2. Download Risk Daemon
[GitHub release or installation package]

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
[Environment variables to set]
- PROJECT_X_API_KEY=your_key_here
- PROJECT_X_USERNAME=trader1

### 5. Initial Configuration
[Create config/system.json, config/accounts.json]

### 6. Install as Windows Service
```bash
python scripts/install_daemon.py
```

### 7. Verify Installation
[How to check daemon is running]

## Troubleshooting
- Error: "Python not found" → [solution]
- Error: "Permission denied" → [solution]
```

### 2. docs/user-guides/admin_guide.md

**For: Admins (Technical)**

```markdown
# Admin Guide

## Starting/Stopping the Daemon

### Start Daemon
```bash
risk-daemon-admin start
```

### Stop Daemon
```bash
risk-daemon-admin stop
```

### Restart Daemon
```bash
risk-daemon-admin restart
```

## Configuring Risk Rules

### View Current Configuration
```bash
risk-daemon-admin config show
```

### Update Max Contracts Rule
```bash
risk-daemon-admin config set-rule max-contracts --limit 10
```

### Enable/Disable Rule
```bash
risk-daemon-admin config enable-rule daily-loss
risk-daemon-admin config disable-rule symbol-block
```

## Viewing Logs

### Live Log Tail
```bash
risk-daemon-admin logs tail
```

### View Enforcement Log
```bash
risk-daemon-admin logs enforcement
```

### View Error Log
```bash
risk-daemon-admin logs errors
```

## Handling Emergencies

### Emergency Kill Switch (Flatten All)
```bash
risk-daemon-admin emergency flatten-all --reason "Market closure"
```

### Manual Override (Temporary Disable)
```bash
risk-daemon-admin override disable --duration 30m --reason "System maintenance"
```

### Restore from Backup
```bash
risk-daemon-admin restore --backup-file path/to/backup.db
```

## Configuration Files

### config/system.json
[Structure and fields explained]

### config/accounts.json
[Per-account configuration]

### config/rules/max-contracts.json
[Rule-specific configuration]
```

### 3. docs/user-guides/trader_guide.md

**For: Traders (Non-Technical)**

```markdown
# Trader Guide: Understanding the Risk Daemon

## What is the Risk Daemon?

The Risk Daemon is your trading guardian. It automatically monitors your positions and enforces risk limits to protect you from excessive losses.

**Think of it as**: A safety net that prevents you from over-trading or taking excessive risk.

## How It Protects You

### 1. Position Limits
- **Max Contracts**: Won't let you hold more than X contracts total
- **Max Per Symbol**: Won't let you over-concentrate in one symbol

### 2. Loss Protection
- **Daily Loss Limit**: Flattens you if you lose more than $X in a day
- **Unrealized Loss**: Closes positions if underwater by $X

### 3. Profit Protection
- **Daily Profit Target**: Takes you out when you hit daily goal
- **Unrealized Profit**: Locks in profits automatically

### 4. Time-Based Rules
- **Trading Hours**: Blocks trading outside 8:30am - 3:00pm CT
- **End-of-Day**: Flattens you at 3:00pm CT if still in positions

### 5. Safety Rules
- **Stop Loss Required**: Must place stop within 2 minutes of entry
- **Cooldown After Loss**: Pause trading after big loss

## What Happens When a Rule Triggers?

### Example 1: Hit Daily Loss Limit
1. Daemon detects you've lost $500 (your limit)
2. **Automatically closes ALL positions**
3. **Locks you out for rest of day**
4. Sends Discord notification: "Daily loss limit reached"

### Example 2: Exceed Position Limit
1. You try to enter 6 contracts (limit is 5)
2. **Order is rejected**
3. Notification: "Max contracts exceeded"

### Example 3: No Stop Loss Placed
1. You enter position without stop loss
2. **Wait 2 minutes**
3. **Daemon automatically flattens position**
4. Notification: "Stop loss not placed in time"

## Can I Override the Daemon?

**Short Answer**: No (by design)

**Why?**: The whole point is protection. If you could override it, you'd defeat the purpose.

**Exception**: Admin can manually override in emergencies.

## Understanding Notifications

### Discord Notifications

You'll receive messages like:
- ✅ "Risk rule triggered: Daily loss limit"
- ✅ "Action taken: Flattened all positions"
- ✅ "Reason: Exceeded $500 daily loss"
- ✅ "Lockout until: 5:00pm CT"

### What Each Notification Means
- **"Flattened"**: All positions closed
- **"Lockout"**: Can't trade until time specified
- **"Rejected"**: New order blocked
- **"Cooldown"**: Pause before next trade allowed

## FAQ

### Q: Why was I flattened?
A: Check Discord. Notification tells you which rule triggered and why.

### Q: Can I trade after being flattened?
A: Depends on the rule. Daily loss = locked until tomorrow. Max contracts = can trade once you're below limit.

### Q: What if I disagree with a rule trigger?
A: Talk to admin. They can review logs and adjust rules if needed.

### Q: Does the daemon ever stop working?
A: It's designed to run 24/7. If it crashes, admin gets alerted immediately.

### Q: What happens if my internet disconnects?
A: Daemon reconnects automatically. Any missed events are caught up.

### Q: Can I see my current limits?
A: Ask admin or check your trader dashboard (if available).
```

### 4. docs/user-guides/troubleshooting_guide.md

**For: Admins**

```markdown
# Troubleshooting Guide

## Common Issues

### Daemon Won't Start
**Symptoms**: Service fails to start, error in logs
**Causes**:
- SDK credentials invalid
- Config file malformed
- Port already in use
**Solutions**:
1. Check logs: `risk-daemon-admin logs errors`
2. Validate config: `risk-daemon-admin config validate`
3. Test SDK connection: `risk-daemon-admin test-connection`

### Tests Failing Unexpectedly
**Symptoms**: Rules not triggering, positions not closing
**Causes**:
- State out of sync
- SDK disconnected
- Config not reloaded
**Solutions**:
1. Check connection: `risk-daemon-admin status`
2. Reconcile state: `risk-daemon-admin reconcile`
3. Reload config: `risk-daemon-admin config reload`

[... Continue for all common issues ...]
```

### 5. docs/user-guides/faq.md

**For: Traders and Admins**

```markdown
# Frequently Asked Questions

## For Traders

**Q: What is the risk daemon?**
A: An automated system that enforces risk limits to protect you from over-trading.

**Q: How does it know when to stop me?**
A: It monitors every trade and position in real-time against configured rules.

**Q: Can I turn it off?**
A: No. That defeats the purpose. Only admin can override in emergencies.

[... 20+ FAQs ...]

## For Admins

**Q: How do I update risk rules?**
A: Use `risk-daemon-admin config set-rule <rule-name> --param value`

**Q: Where are logs stored?**
A: `logs/daemon.log`, `logs/enforcement.log`, `logs/audit.log`

[... 20+ FAQs ...]
```

## ✅ Success Criteria

You succeed when:
- [ ] Installation guide is step-by-step clear
- [ ] Admin guide covers all CLI commands
- [ ] Trader guide is non-technical and friendly
- [ ] Troubleshooting covers common issues
- [ ] FAQ answers realistic questions
- [ ] All documentation is ready for production launch

## 📊 Output Summary Template

```
✅ Documentation Complete

Created 5 User Guides:
- installation_guide.md (step-by-step setup)
- admin_guide.md (CLI commands, config, emergency procedures)
- trader_guide.md (non-technical, explains protections)
- troubleshooting_guide.md (common issues + solutions)
- faq.md (20+ questions for traders, 20+ for admins)

Documentation Characteristics:
- Installation: Technical, step-by-step
- Admin: Technical, command reference
- Trader: Non-technical, friendly tone
- Troubleshooting: Problem-solution format
- FAQ: Question-answer, searchable

Ready for Production Launch: ✅
```

---

## 🚀 Ready to Start?

Write documentation that makes complex systems understandable. Traders and admins depend on your clarity.

**BEGIN DOCUMENTATION WRITING NOW.**
