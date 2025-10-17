# 🖥️ Terminal Setup Guide

**Visual guide for setting up your 6-terminal workspace**

---

## Option 1: Windows Terminal (Recommended)

### Layout: 2x3 Grid

```
┌─────────────────────────────┬─────────────────────────────┐
│                             │                             │
│   Terminal 1: MAIN          │   Terminal 2: SDK Analysis  │
│   (rm-test-orchestrator)    │   (sdk-deep-analyzer)       │
│                             │                             │
│   Status: 🟢 RUNNING        │   Status: START NOW         │
│                             │                             │
├─────────────────────────────┼─────────────────────────────┤
│                             │                             │
│   Terminal 3: Performance   │   Terminal 4: Security      │
│   (performance-strategist)  │   (security-hardener)       │
│                             │                             │
│   Status: START NOW         │   Status: START NOW         │
│                             │                             │
├─────────────────────────────┼─────────────────────────────┤
│                             │                             │
│   Terminal 5: Documentation │   Terminal 6: Deployment    │
│   (documentation-writer)    │   (deployment-planner)      │
│                             │                             │
│   Status: START NOW         │   Status: START NOW         │
│                             │                             │
└─────────────────────────────┴─────────────────────────────┘
```

### Setup Steps

**1. Open Windows Terminal**
```
Win + X → Windows Terminal
```

**2. Create Split Layout**
```
# Split right (Terminal 2)
Ctrl + Shift + D

# Split down in left pane (Terminal 3)
Alt + Shift + D

# Split right in Terminal 3 (Terminal 4)
Ctrl + Shift + D

# Split down in Terminal 1 (Terminal 5)
Alt + Shift + D

# Split right in Terminal 5 (Terminal 6)
Ctrl + Shift + D
```

**3. Navigate Between Terminals**
```
Alt + ← → ↑ ↓   (Arrow keys)
```

**4. Resize Panes**
```
Alt + Shift + ← → ↑ ↓   (Arrow keys)
```

---

## Option 2: tmux (Advanced Users)

### Setup Script

Save this as `setup-terminals.sh`:

```bash
#!/bin/bash

# Create new tmux session
tmux new-session -d -s risk-daemon

# Rename first window
tmux rename-window -t risk-daemon:0 'Agents'

# Split into 6 panes
tmux split-window -h
tmux split-window -v
tmux select-pane -t 0
tmux split-window -v
tmux select-pane -t 2
tmux split-window -v
tmux select-pane -t 4
tmux split-window -v

# Set pane titles (requires tmux 3.0+)
tmux select-pane -t 0 -T "MAIN"
tmux select-pane -t 1 -T "SDK Analysis"
tmux select-pane -t 2 -T "Performance"
tmux select-pane -t 3 -T "Security"
tmux select-pane -t 4 -T "Documentation"
tmux select-pane -t 5 -T "Deployment"

# CD to project directory in each pane
for i in {0..5}; do
    tmux send-keys -t risk-daemon:0.$i "cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon" C-m
done

# Attach to session
tmux attach-session -t risk-daemon
```

### Run Setup Script

```bash
chmod +x setup-terminals.sh
./setup-terminals.sh
```

### tmux Navigation

```
Ctrl+b ←→↑↓        Navigate panes
Ctrl+b z           Zoom/unzoom current pane
Ctrl+b q           Show pane numbers
Ctrl+b d           Detach (session keeps running)
tmux attach        Reattach to session
```

---

## Option 3: Separate Windows (Simple)

### Just Open 6 Terminal Windows

**Pros:**
- Simplest setup
- Can arrange on multiple monitors
- Easy to see all at once

**Cons:**
- Takes up more screen space
- Harder to organize

**Setup:**
1. Open Terminal 1 (already running rm-test-orchestrator)
2. Open Terminal 2, run SDK analyzer
3. Open Terminal 3, run Performance strategist
4. Open Terminal 4, run Security hardener
5. Open Terminal 5, run Documentation writer
6. Open Terminal 6, run Deployment planner

**Naming Windows:**
Right-click terminal title bar → Rename

---

## 📋 Start Commands for Each Terminal

### Terminal 1: MAIN (Already Running)
```bash
# rm-test-orchestrator is running
# Wait for completion message:
# "✅ rm-test-orchestrator COMPLETE"
```

### Terminal 2: SDK Analysis
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/sdk-deep-analyzer.md
# Expected runtime: 30-60 minutes
```

### Terminal 3: Performance Strategy
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/performance-strategist.md
# Expected runtime: 30-60 minutes
```

### Terminal 4: Security Hardening
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/security-hardener.md
# Expected runtime: 45-90 minutes
```

### Terminal 5: Documentation
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/documentation-writer.md
# Expected runtime: 60-90 minutes
```

### Terminal 6: Deployment Planning
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon
cat agents/background-research/deployment-planner.md
# Expected runtime: 45-60 minutes
```

---

## 🎨 Color Coding (Optional)

### Windows Terminal: Set Background Colors

Edit `settings.json`:

```json
{
  "profiles": {
    "list": [
      {
        "name": "Terminal 1 - MAIN",
        "colorScheme": "One Half Dark",
        "backgroundImage": null
      },
      {
        "name": "Terminal 2 - SDK",
        "colorScheme": "Solarized Dark",
        "backgroundImage": null
      },
      {
        "name": "Terminal 3 - Performance",
        "colorScheme": "Tango Dark",
        "backgroundImage": null
      },
      {
        "name": "Terminal 4 - Security",
        "colorScheme": "Campbell",
        "backgroundImage": null
      },
      {
        "name": "Terminal 5 - Docs",
        "colorScheme": "Vintage",
        "backgroundImage": null
      },
      {
        "name": "Terminal 6 - Deploy",
        "colorScheme": "Retro",
        "backgroundImage": null
      }
    ]
  }
}
```

---

## 🔔 Notifications (Optional)

### Get Notified When Agents Complete

**Linux/WSL:**
```bash
# Install notification tool
sudo apt-get install libnotify-bin

# Add to agent command
cat agents/background-research/sdk-deep-analyzer.md && \
notify-send "Agent Complete" "SDK Deep Analyzer finished"
```

**Windows:**
```powershell
# Use PowerShell toast notifications
# Add to agent command (PowerShell):
cat agents/background-research/sdk-deep-analyzer.md; `
Add-Type -AssemblyName System.Windows.Forms; `
[System.Windows.Forms.MessageBox]::Show("SDK Deep Analyzer Complete")
```

---

## 📊 Monitoring Dashboard (Advanced)

### Create a Status Dashboard

Create `check-status.sh`:

```bash
#!/bin/bash

clear
echo "════════════════════════════════════════════════════════"
echo "  Risk Daemon Agent Status Dashboard"
echo "  $(date)"
echo "════════════════════════════════════════════════════════"
echo

echo "Terminal 1: MAIN"
if pgrep -f "rm-test-orchestrator" > /dev/null; then
    echo "  Status: 🟢 RUNNING"
else
    echo "  Status: ⚪ IDLE"
fi
echo

echo "Terminal 2: SDK Analysis"
if [ -f "docs/research/sdk_capability_deep_dive.md" ]; then
    echo "  Status: ✅ COMPLETE"
elif pgrep -f "sdk-deep-analyzer" > /dev/null; then
    echo "  Status: 🔵 RUNNING"
else
    echo "  Status: ⏸️  NOT STARTED"
fi
echo

echo "Terminal 3: Performance Strategy"
if [ -f "docs/research/performance_benchmarks.md" ]; then
    echo "  Status: ✅ COMPLETE"
elif pgrep -f "performance-strategist" > /dev/null; then
    echo "  Status: 🔵 RUNNING"
else
    echo "  Status: ⏸️  NOT STARTED"
fi
echo

echo "Terminal 4: Security Hardening"
if [ -f "docs/research/security_audit.md" ]; then
    echo "  Status: ✅ COMPLETE"
elif pgrep -f "security-hardener" > /dev/null; then
    echo "  Status: 🔵 RUNNING"
else
    echo "  Status: ⏸️  NOT STARTED"
fi
echo

echo "Terminal 5: Documentation"
if [ -f "docs/user-guides/installation_guide.md" ]; then
    echo "  Status: ✅ COMPLETE"
elif pgrep -f "documentation-writer" > /dev/null; then
    echo "  Status: 🔵 RUNNING"
else
    echo "  Status: ⏸️  NOT STARTED"
fi
echo

echo "Terminal 6: Deployment Planning"
if [ -f "docs/deployment/deployment_strategy.md" ]; then
    echo "  Status: ✅ COMPLETE"
elif pgrep -f "deployment-planner" > /dev/null; then
    echo "  Status: 🔵 RUNNING"
else
    echo "  Status: ⏸️  NOT STARTED"
fi
echo

echo "════════════════════════════════════════════════════════"
echo "Next check: Run ./check-status.sh again"
echo "════════════════════════════════════════════════════════"
```

Run every 5 minutes:
```bash
chmod +x check-status.sh
watch -n 300 ./check-status.sh
```

---

## 🎯 Quick Terminal Setup (Copy-Paste)

**If you just want to get started fast:**

1. **Keep Terminal 1 running** (rm-test-orchestrator already going)

2. **Open 5 new terminals and paste these commands:**

**Terminal 2:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon && cat agents/background-research/sdk-deep-analyzer.md
```

**Terminal 3:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon && cat agents/background-research/performance-strategist.md
```

**Terminal 4:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon && cat agents/background-research/security-hardener.md
```

**Terminal 5:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon && cat agents/background-research/documentation-writer.md
```

**Terminal 6:**
```bash
cd /mnt/c/Users/jakers/Desktop/RM_SDK1/risk-daemon && cat agents/background-research/deployment-planner.md
```

3. **Wait and monitor** - Check every 30 minutes

---

## ✅ Setup Verification

After starting all terminals, verify:

```
[ ] Terminal 1: Shows rm-test-orchestrator output
[ ] Terminal 2: Shows sdk-deep-analyzer output
[ ] Terminal 3: Shows performance-strategist output
[ ] Terminal 4: Shows security-hardener output
[ ] Terminal 5: Shows documentation-writer output
[ ] Terminal 6: Shows deployment-planner output
[ ] All terminals show activity (text scrolling)
[ ] No error messages in red
```

If any terminal shows errors:
1. Read the error message
2. Check the agent MD file for requirements
3. Fix the issue (missing dependency, wrong path, etc.)
4. Restart that terminal

---

**You're all set! Let the agents work while you monitor progress.**

**Next:** Check QUICK_REFERENCE.md for what to do every 30 minutes.
