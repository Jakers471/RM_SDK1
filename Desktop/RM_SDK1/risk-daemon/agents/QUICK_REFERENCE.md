# 🚀 Risk Daemon Agent Quick Reference Card

**Keep this open in a separate window for at-a-glance reference**

---

## 📍 WHERE AM I? (Current Status)

```
✅ DONE: gap-closer
🟢 NOW: rm-test-orchestrator (Terminal 1)
📋 NEXT: rm-developer (After orchestrator completes)
🔵 BACKGROUND: Start 5 agents NOW (Terminals 2-6)
```

---

## 🎯 WHAT TO DO RIGHT NOW

### Terminal 1 (Main) - Already Running ✅
```bash
# rm-test-orchestrator is creating tests
# Wait for completion message
# Expected time: 30-60 minutes
```

### Terminals 2-6 (Background) - START NOW! 🔵

**Terminal 2:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/sdk-deep-analyzer.md
```

**Terminal 3:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/performance-strategist.md
```

**Terminal 4:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/security-hardener.md
```

**Terminal 5:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/documentation-writer.md
```

**Terminal 6:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/deployment-planner.md
```

---

## ⏰ CHECK EVERY 30 MINUTES

```
┌─────────────────────────────────────────────────┐
│ Terminal 1: Has rm-test-orchestrator finished? │
│   YES → Run rm-developer                       │
│   NO  → Keep waiting                            │
│                                                 │
│ Terminals 2-6: Any completions or errors?      │
│   Completion → Review output document          │
│   Error → Check error message, restart if needed│
└─────────────────────────────────────────────────┘
```

---

## 🔄 STANDARD WORKFLOW (Repeat for Each Component)

```
1. gap-closer          → Creates architecture (1 hour)
2. rm-test-orchestrator → Creates tests (1 hour)
3. rm-developer        → Implements code (3 hours)
4. Verify green        → Check tests pass (5 mins)
5. Commit              → Save progress
6. Next component      → Repeat
```

---

## 📊 PROGRESS TRACKER (Update Daily)

### Phase 1 Components

```
[✅] Configuration System  (Day 1-4)
[ ] CLI System            (Day 5-8)
[ ] Service Wrapper       (Day 9-12)
[ ] Monitoring System     (Day 13-16)
[ ] State Persistence     (Day 17-20)
```

### Background Research

```
[🔵] SDK Analysis         (Running...)
[🔵] Performance Strategy (Running...)
[🔵] Security Hardening   (Running...)
[🔵] Documentation        (Running...)
[🔵] Deployment Planning  (Running...)
```

---

## 🆘 QUICK TROUBLESHOOTING

### Tests Failing?
```bash
# Run debugger
cat agents/utilities/test-failure-debugger.md
```

### Agent Stuck?
```bash
# Press Ctrl+C
# Review agent MD file
# Restart agent
```

### Coverage Too Low?
```bash
# Run coverage enforcer
cat agents/1-current-implementation/test-coverage-enforcer.md
```

---

## 📞 WHEN TO ASK FOR HELP

```
❌ Agent running >2x expected time
❌ Errors you don't understand
❌ Tests won't pass after 3 attempts
❌ Security HIGH severity found
❌ Unsure which agent to run next

✅ Review EXECUTION_MASTER_GUIDE.md first
✅ Check decision trees
✅ Then ask for help with specific error
```

---

## 🎯 TODAY'S GOALS

```
[ ] 5 background agents running (Terminals 2-6)
[ ] rm-test-orchestrator completes (Terminal 1)
[ ] 48 tests created, all RED
[ ] rm-developer starts implementing
[ ] Evening: Check background agent progress
```

---

## ⏭️ TOMORROW'S GOALS

```
[ ] rm-developer completes Configuration System
[ ] 48/48 tests GREEN
[ ] Coverage ≥85%
[ ] Commit Phase 1.1 complete
[ ] Start CLI System (Phase 1.2)
```

---

## 📋 END-OF-DAY CHECKLIST

```
[ ] All agents completed or still running (no crashes)
[ ] Progress logged (progress.log file)
[ ] Current status known (which phase/component)
[ ] Tomorrow's plan clear
[ ] Terminal sessions saved (tmux/screen)
```

---

## 🔑 KEY FILES TO WATCH

```
📁 architecture/          → Designs from gap-closer
📁 tests/unit/           → Unit tests (fast)
📁 tests/integration/    → Integration tests
📁 src/                  → Implementation code
📄 TEST_NOTES.md         → Test coverage summary
📄 progress.log          → Your daily log
```

---

## 💡 REMEMBER

- **Background agents = Fire and forget** (run once at start)
- **Main workflow = Sequential** (one at a time)
- **Commit often** (after each green component)
- **Check every 30 mins** (but don't micromanage)
- **Read the guide** (EXECUTION_MASTER_GUIDE.md for details)

---

**Current Phase:** Phase 1 - Mocked Implementation
**Current Component:** Configuration System
**Current Agent:** rm-test-orchestrator (Terminal 1)
**Background Status:** 5 agents should be running (Terminals 2-6)

**Next Check:** 30 minutes from now
