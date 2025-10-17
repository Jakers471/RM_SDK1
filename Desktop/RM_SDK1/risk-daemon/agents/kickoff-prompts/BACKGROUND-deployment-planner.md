# BACKGROUND RESEARCH: Deployment Planner Kickoff

**Agent**: deployment-planner
**Model**: opus
**Priority**: Background (PARALLEL with Phase 1)
**Estimated Time**: 1-2 hours
**Status**: Ready to run

---

## 📖 FIRST: Read Your Agent Definition

**CRITICAL**: Before starting, read your complete agent definition:
```
agents/background-research/deployment-planner.md
```

This file contains your full mission, constraints, and quality standards. The kickoff below is a quick-start summary.

---

## 🎯 Your Mission

You are the **deployment-planner** agent. Design safe, repeatable production deployment strategy with comprehensive rollback capability. Account for zero-downtime requirement (can't stop trading).

## 📚 Required Reading

1. **docs/architecture/** (What's being deployed)
   - Understand: Daemon components, dependencies, state management
   - Extract: Deployment constraints

2. **Industry Best Practices**
   - Research: Canary deployments, blue-green deployment, feature flags
   - Trading system context: Zero-downtime critical

3. **Risk Tolerance**
   - Trading system = HIGH RISK
   - Can't afford downtime during market hours
   - Must have instant rollback capability

## 📝 Your Deliverables

### 1. docs/deployment/deployment_strategy.md

**Deployment Approach**: Canary Deployment (Recommended for Trading Systems)

```markdown
# Deployment Strategy

## Why Canary Deployment?

Trading systems require **zero-downtime** and **instant rollback**. Canary deployment:
1. Deploy to 1 test account first
2. Monitor for 24 hours
3. Gradually rollout to 10%, 50%, 100% of accounts
4. Rollback instantly if issues detected

## Staging Environment

### Requirements
- Identical to production (same OS, Python version, dependencies)
- Connected to SDK test broker account
- Realistic test data (historical fills, positions)

### Setup
```bash
# Clone production config
cp -r /prod/config /staging/config

# Use staging credentials
export PROJECT_X_API_KEY=staging_key
export PROJECT_X_USERNAME=test_trader

# Deploy staging build
./scripts/deploy_staging.sh
```

## Pre-Production Validation

Before any production deployment:
- [ ] All tests pass (mocked + live integration)
- [ ] Coverage ≥85%
- [ ] Performance benchmarks met
- [ ] Security audit passed
- [ ] Documentation complete

## Go-Live Procedure (Step-by-Step)

### Phase 1: Canary (1 Test Account, 24h)
1. **Deploy to canary account**
   ```bash
   ./scripts/deploy_canary.sh --account test_trader_1
   ```
2. **Monitor canary metrics**
   - Event processing latency
   - Rule evaluation accuracy
   - Enforcement action correctness
   - Memory/CPU usage
3. **Validation checklist**
   - [ ] All rules trigger correctly
   - [ ] No false positives/negatives
   - [ ] Reconnection works after disconnect
   - [ ] State recovers after restart
4. **Decision: Proceed or Rollback?**
   - If any issues: ROLLBACK immediately
   - If clean 24h: Proceed to Phase 2

### Phase 2: Limited Rollout (10% of Accounts, 48h)
1. **Deploy to 10% of accounts**
   ```bash
   ./scripts/deploy_percentage.sh --percent 10
   ```
2. **Monitor aggregate metrics**
   - Compare canary vs new deployments
   - Watch for anomalies
3. **Decision: Proceed or Rollback?**

### Phase 3: Majority Rollout (50% of Accounts, 48h)
1. **Deploy to 50% of accounts**
2. **Monitor at scale**
3. **Decision: Proceed or Rollback?**

### Phase 4: Full Rollout (100% of Accounts)
1. **Deploy to remaining accounts**
2. **Monitor for 1 week**
3. **Mark deployment complete**

## Smoke Tests After Deployment

Immediately after each deployment phase:
```bash
# Test 1: Daemon is running
curl http://localhost:8080/health

# Test 2: SDK connection active
risk-daemon-admin test-connection

# Test 3: Events being processed
risk-daemon-admin status --show-events

# Test 4: Rule evaluation working
risk-daemon-admin test-rule max-contracts

# Test 5: State persistence working
risk-daemon-admin test-persistence
```

## Monitoring During Deployment

**Key Metrics to Watch**:
- Event processing latency (should be <100ms P95)
- Error rate (should be <0.1%)
- Memory usage (should be <500MB)
- Connection status (should be "connected")

**Alert Thresholds**:
- Latency >200ms → WARNING
- Error rate >1% → CRITICAL, consider rollback
- Memory >700MB → WARNING
- Disconnected >5min → CRITICAL

**Dashboard**: Real-time graphs of all metrics
```

### 2. docs/deployment/rollback_procedure.md

**Instant Rollback Capability**:

```markdown
# Rollback Procedure

## When to Rollback

**IMMEDIATELY rollback if**:
- Error rate >1%
- Daemon crashes in production
- Rules not triggering correctly
- State corruption detected
- Performance degradation >50%
- Security incident

## Rollback Steps (5 Minutes Max)

### Step 1: Stop New Deployment (30s)
```bash
./scripts/stop_deployment.sh
```

### Step 2: Revert to Previous Version (2min)
```bash
# Rollback daemon binary
./scripts/rollback_daemon.sh --to-version v1.2.0

# Rollback configuration
./scripts/rollback_config.sh --to-commit abc123

# Restart daemon
./scripts/restart_daemon.sh
```

### Step 3: Verify Rollback Success (1min)
```bash
# Check version
risk-daemon-admin --version  # Should show v1.2.0

# Check connection
risk-daemon-admin test-connection  # Should succeed

# Check rule evaluation
risk-daemon-admin test-rule max-contracts  # Should pass
```

### Step 4: State Reconciliation (1min)
```bash
# Reconcile positions with broker
risk-daemon-admin reconcile-state

# Verify state consistency
risk-daemon-admin verify-state
```

### Step 5: Notify Stakeholders (30s)
```bash
# Send alert
./scripts/send_alert.sh "Deployment rolled back to v1.2.0"
```

## Database Rollback

If schema changed:
```bash
# Rollback database migrations
./scripts/db_rollback.sh --to-version 5

# Verify schema
risk-daemon-admin verify-db
```

## Communication Plan

**Notify**:
- Traders (Discord): "System restored to previous version"
- Admins (Email): "Rollback completed, v1.2.0 active"
- Management (Slack): "Deployment issue, rolled back successfully"
```

### 3. docs/deployment/deployment_checklist.md

**Pre/During/Post Deployment**:

```markdown
# Deployment Checklist

## Pre-Deployment (1 Day Before)

### Code & Tests
- [ ] All tests passing (100%)
- [ ] Coverage ≥85%
- [ ] No skipped or failing tests
- [ ] Performance benchmarks met
- [ ] Security audit passed

### Configuration
- [ ] Config files reviewed and validated
- [ ] Credentials rotated if needed
- [ ] Environment variables set correctly
- [ ] Feature flags configured

### Documentation
- [ ] Release notes written
- [ ] Breaking changes documented
- [ ] Runbook updated
- [ ] Rollback procedure tested

### Backups
- [ ] Database backed up
- [ ] Config files backed up
- [ ] Current version tagged in git
- [ ] Backup restore tested

### Team Readiness
- [ ] Deployment team on call
- [ ] Rollback team on standby
- [ ] Traders notified of deployment window
- [ ] Monitoring dashboard ready

## During Deployment

### Phase 1: Canary
- [ ] Deploy to canary account
- [ ] Smoke tests pass
- [ ] Monitor for 24 hours
- [ ] Validate metrics
- [ ] Decision: Proceed or rollback

### Phase 2-4: Gradual Rollout
- [ ] Deploy to next percentage
- [ ] Smoke tests pass each phase
- [ ] Monitor metrics continuously
- [ ] No anomalies detected

## Post-Deployment (1 Week After)

### Validation
- [ ] All accounts on new version
- [ ] No rollbacks required
- [ ] Metrics stable
- [ ] No trader complaints
- [ ] Performance meets benchmarks

### Documentation
- [ ] Deployment retrospective completed
- [ ] Lessons learned documented
- [ ] Runbook updated
- [ ] Known issues documented

### Cleanup
- [ ] Old version backups archived
- [ ] Deployment logs archived
- [ ] Canary environment cleaned up
```

### 4. docs/deployment/disaster_recovery.md

**Emergency Scenarios**:

```markdown
# Disaster Recovery Plan

## Scenario 1: Daemon Crashes in Production

**Symptoms**: Daemon process exits unexpectedly
**Impact**: No risk protection (CRITICAL)
**Recovery**:
1. Auto-restart (NSSM handles this)
2. If restart fails 3x: Alert admin
3. Admin investigates logs
4. If bug: Rollback to previous version
5. If config: Fix config, restart

**Recovery Time**: <5 minutes (auto-restart) or <30 minutes (manual)

## Scenario 2: SDK Disconnects

**Symptoms**: Lost connection to broker
**Impact**: No position updates (HIGH)
**Recovery**:
1. Daemon auto-reconnects (exponential backoff)
2. Reconcile state after reconnection
3. If repeated disconnects: Alert admin
4. Admin checks: SDK status, credentials, network

**Recovery Time**: <2 minutes (auto-reconnect)

## Scenario 3: Config File Corrupted

**Symptoms**: Daemon won't start, config validation fails
**Impact**: Can't protect (CRITICAL)
**Recovery**:
1. Restore config from backup
2. Validate config
3. Restart daemon
4. Verify rules active

**Recovery Time**: <10 minutes

## Scenario 4: Database Corruption

**Symptoms**: State persistence errors
**Impact**: Lost state on restart (HIGH)
**Recovery**:
1. Stop daemon
2. Restore database from backup
3. Reconcile state with broker
4. Restart daemon
5. Verify state consistency

**Recovery Time**: <20 minutes

## Emergency Contacts

- **Admin On-Call**: [phone/email]
- **SDK Support**: [phone/email]
- **Escalation**: [manager phone/email]

## Manual Override Procedures

If daemon must be disabled in emergency:
```bash
# Emergency shutdown
risk-daemon-admin emergency shutdown --reason "Manual intervention required"

# Flatten all positions first (protect trader)
risk-daemon-admin emergency flatten-all --reason "System emergency"
```
```

## ✅ Success Criteria

You succeed when:
- [ ] Deployment strategy accounts for zero-downtime
- [ ] Rollback procedure is <5 minutes
- [ ] Canary deployment plan detailed
- [ ] Smoke tests defined for each phase
- [ ] Disaster recovery covers all scenarios
- [ ] Emergency contacts documented

## 📊 Output Summary Template

```
✅ Deployment Planning Complete

Created 4 Deployment Documents:
- deployment_strategy.md (canary deployment, 4 phases)
- rollback_procedure.md (<5 min rollback)
- deployment_checklist.md (pre/during/post checks)
- disaster_recovery.md (4 emergency scenarios)

Deployment Strategy:
- Approach: Canary deployment
- Phases: Canary (1 account) → 10% → 50% → 100%
- Timeline: 5-7 days total
- Rollback: <5 minutes

Disaster Recovery:
- Daemon crash: <5min recovery
- SDK disconnect: <2min auto-reconnect
- Config corruption: <10min recovery
- Database corruption: <20min recovery

Emergency Procedures:
- Manual override: ✅
- Emergency shutdown: ✅
- Emergency flatten: ✅

Ready for Production Deployment: ✅
```

---

## 🚀 Ready to Start?

Design deployment strategy that ensures safe, repeatable production rollout. Trading can't stop - plan accordingly.

**BEGIN DEPLOYMENT PLANNING NOW.**
