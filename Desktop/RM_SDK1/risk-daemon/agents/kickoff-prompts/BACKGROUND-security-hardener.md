# BACKGROUND RESEARCH: Security Hardener Kickoff

**Agent**: security-hardener
**Model**: opus
**Priority**: Background (PARALLEL with Phase 1)
**Estimated Time**: 1-2 hours
**Status**: Ready to run

---

## 📖 FIRST: Read Your Agent Definition

**CRITICAL**: Before starting, read your complete agent definition:
```
agents/background-research/security-hardener.md
```

This file contains your full mission, constraints, and quality standards. The kickoff below is a quick-start summary.

---

## 🎯 Your Mission

You are the **security-hardener** agent. Conduct comprehensive security audit of the risk daemon and create hardening plan for production deployment.

## 📚 Required Reading

1. **src/** (All source code)
   - Review for: Hardcoded credentials, SQL injection, input validation gaps
   - Check: Authentication mechanisms, error handling, logging

2. **docs/architecture/** (Design specifications)
   - Understand: Authentication flow, API access, data storage
   - Identify: Security-critical components

3. **OWASP Top 10** (Security best practices)
   - Reference: https://owasp.org/www-project-top-ten/
   - Apply to trading system context

4. **docs/audits/** (Audit findings)
   - Look for: Security-related issues mentioned

## 📝 Your Deliverables

### 1. docs/research/security_audit.md

**Vulnerability Assessment** (categorize by severity):

#### CRITICAL Vulnerabilities
- [ ] Hardcoded API keys or credentials
- [ ] SQL injection points
- [ ] Authentication bypass
- [ ] Sensitive data in logs

#### HIGH Vulnerabilities
- [ ] Weak password requirements
- [ ] Missing input validation
- [ ] Unencrypted data transmission
- [ ] Insufficient access controls

#### MEDIUM Vulnerabilities
- [ ] Information disclosure in error messages
- [ ] Missing rate limiting
- [ ] Insufficient logging for security events
- [ ] Session management issues

#### LOW Vulnerabilities
- [ ] Verbose error messages
- [ ] Missing security headers
- [ ] Outdated dependencies

**Threat Model**:
- **Who**: Malicious trader, compromised admin, external attacker
- **What**: Bypass risk rules, steal credentials, DoS attack, data exfiltration
- **How**: API abuse, config manipulation, SDK spoofing, log injection

**Attack Vectors**:
1. **Config File Manipulation**: Attacker modifies risk rules to disable protection
2. **Admin CLI Compromise**: Weak password, gain full control
3. **Log Injection**: Inject fake enforcement logs
4. **SDK Spoofing**: Send fake fill events to trigger unwanted closures
5. **DoS**: Flood event bus with fake events

### 2. docs/research/security_hardening_plan.md

**Mitigation Strategies** for each vulnerability:

#### Credential Management
- ✅ **Action**: Move all credentials to environment variables
- ✅ **Action**: Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
- ✅ **Action**: Rotate credentials periodically
- ✅ **Action**: Never log credentials

#### Input Validation
- ✅ **Action**: Validate ALL external inputs (SDK events, config files, CLI commands)
- ✅ **Action**: Use JSON schema for config validation
- ✅ **Action**: Sanitize log inputs (prevent log injection)
- ✅ **Action**: Whitelist allowed values where possible

#### Authentication & Authorization
- ✅ **Action**: Strong password requirements for Admin CLI (12+ chars, complexity)
- ✅ **Action**: Password hashing with bcrypt/argon2
- ✅ **Action**: Implement session timeouts
- ✅ **Action**: Multi-factor authentication for admin access (optional)
- ✅ **Action**: Principle of least privilege (trader vs admin access)

#### Rate Limiting
- ✅ **Action**: Limit CLI command rate (10 commands/minute)
- ✅ **Action**: Limit config reload rate (1/minute)
- ✅ **Action**: Protect against event flood (circuit breaker)

#### Encryption
- ✅ **Action**: Encrypt sensitive data at rest (SQLite database encryption)
- ✅ **Action**: Use TLS for all network communication
- ✅ **Action**: Encrypt admin password in config

#### Audit Logging
- ✅ **Action**: Log ALL security events (auth attempts, config changes, enforcement actions)
- ✅ **Action**: Separate security log (tamper-evident)
- ✅ **Action**: Log to remote server (prevent local tampering)
- ✅ **Action**: Include: timestamp, user, action, result

#### Error Handling
- ✅ **Action**: Generic error messages to users (no stack traces)
- ✅ **Action**: Detailed errors only in secure logs
- ✅ **Action**: Fail securely (deny on error, not allow)

#### Code Security
- ✅ **Action**: SQL parameterized queries only (no string concatenation)
- ✅ **Action**: Avoid eval() or exec() (code injection risk)
- ✅ **Action**: Dependency vulnerability scanning (npm audit, pip audit)

### 3. docs/research/security_checklist.md

**Pre-Production Security Review**:

```markdown
## Authentication & Authorization
- [ ] No hardcoded credentials in code
- [ ] Credentials stored in environment variables or secrets manager
- [ ] Admin password meets complexity requirements
- [ ] Session timeouts implemented
- [ ] Trader vs Admin access properly separated

## Input Validation
- [ ] All SDK events validated before processing
- [ ] All config file inputs validated with JSON schema
- [ ] All CLI inputs sanitized
- [ ] Whitelist validation where applicable

## Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] Network communication uses TLS
- [ ] No sensitive data in logs (passwords, API keys)
- [ ] Database backups encrypted

## Logging & Monitoring
- [ ] Security events logged
- [ ] Log injection prevented (sanitized inputs)
- [ ] Logs sent to tamper-proof remote location
- [ ] Alerting on suspicious activity

## Error Handling
- [ ] Generic errors to users
- [ ] Detailed errors only in secure logs
- [ ] Fail-secure behavior (deny on error)

## Code Security
- [ ] SQL parameterized queries only
- [ ] No eval()/exec() usage
- [ ] Dependencies scanned for vulnerabilities
- [ ] Latest security patches applied

## Network Security
- [ ] Localhost-only for IPC (no remote access)
- [ ] Rate limiting on all APIs
- [ ] Circuit breaker for event flood
- [ ] Firewall rules configured

## Compliance (if applicable)
- [ ] GDPR compliance (trader data protection)
- [ ] Financial regulation compliance
- [ ] Audit trail for all trading decisions
```

**Penetration Testing Plan**:
- [ ] Attempt SQL injection on config inputs
- [ ] Brute-force admin password
- [ ] Attempt to bypass authentication
- [ ] Inject malicious log entries
- [ ] Send fake SDK events (spoofing)
- [ ] DoS attack via event flood

**Vulnerability Scanning**:
- [ ] Run: `pip audit` for Python dependency vulns
- [ ] Run: `bandit` for Python code security issues
- [ ] Run: `safety check` for known vulnerabilities

## ✅ Success Criteria

You succeed when:
- [ ] All vulnerabilities categorized by severity
- [ ] Threat model documents realistic attack scenarios
- [ ] Hardening plan with specific, actionable mitigations
- [ ] Security checklist ready for pre-production review
- [ ] Penetration testing plan defined

## 📊 Output Summary Template

```
✅ Security Audit Complete

Created 3 Research Documents:
- security_audit.md (vulnerabilities identified and categorized)
- security_hardening_plan.md (mitigation strategies)
- security_checklist.md (pre-production review checklist)

Vulnerabilities Found:
- CRITICAL: [count]
- HIGH: [count]
- MEDIUM: [count]
- LOW: [count]

Top 3 Security Concerns:
1. [Most critical issue]
2. [Second most critical]
3. [Third most critical]

Hardening Actions Required:
- [X] credential management improvements
- [X] input validation enhancements
- [X] authentication strengthening
- [X] audit logging implementation

Penetration Testing Plan: ✅
Security Checklist Ready: ✅

Ready for Security Hardening: ✅
```

---

## 🚀 Ready to Start?

Audit the system. Find vulnerabilities. Create hardening plan. Production security depends on your thoroughness.

**BEGIN SECURITY AUDIT NOW.**
