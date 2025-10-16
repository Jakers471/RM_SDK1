# Data Flow Diagrams and Decision Trees

## Overview

This document provides visual representations of how data flows through the Risk Manager Daemon, decision trees for rule enforcement, and sequence diagrams for critical operations. These diagrams complement the textual architecture documents and help implementers understand the system's runtime behavior.

---

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Risk Manager Daemon                       │
│                     (Windows Service Process)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ SDK Adapter  │ ───> │  Event Bus   │ ───> │ Risk Engine  │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         ▲                      │                      │          │
│         │                      │                      ▼          │
│         │                      ▼              ┌──────────────┐  │
│  ┌──────────────┐      ┌──────────────┐      │ Enforcement  │  │
│  │   TopstepX   │      │    State     │      │    Engine    │  │
│  │   (Broker)   │      │   Manager    │      └──────────────┘  │
│  └──────────────┘      └──────────────┘              │          │
│         ▲                      ▲                      │          │
│         │                      │                      │          │
│         └──────────────────────┴──────────────────────┘          │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ Config Mgr   │      │ Notification │      │   Logger     │  │
│  └──────────────┘      │   Service    │      └──────────────┘  │
│                        └──────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   External Channels    │
                    │  Discord / Telegram    │
                    └────────────────────────┘

         ┌────────────────┐              ┌────────────────┐
         │   Admin CLI    │              │  Trader CLI    │
         │   (Password)   │              │  (Read-Only)   │
         └────────────────┘              └────────────────┘
                 │                                │
                 └────────────────┬───────────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │     IPC      │
                          │ (Named Pipe) │
                          └──────────────┘
```

---

## 2. Event Flow Pipeline

### Fill Event Flow (New Position Opened)

```
Broker (TopstepX)
    │
    │ onFill event
    ▼
SDK Adapter
    │
    │ Normalize event data
    ▼
Event Bus
    │
    ├──> State Manager Handler
    │        │ Add position to state
    │        │ Update position count
    │        ▼
    │    State updated
    │
    ├──> Risk Engine Handler
    │        │
    │        │ Get current state
    │        ▼
    │    Evaluate all applicable rules:
    │        │
    │        ├─> MaxContracts rule
    │        │       │ Count total contracts
    │        │       │ If > limit → VIOLATION
    │        │       ▼
    │        │   Violation detected
    │        │
    │        ├─> MaxContractsPerInstrument rule
    │        │       │ Count contracts for this symbol
    │        │       │ If > limit → VIOLATION
    │        │       ▼
    │        │   Violation detected
    │        │
    │        ├─> SymbolBlock rule
    │        │       │ Check if symbol blocked
    │        │       │ If blocked → VIOLATION
    │        │       ▼
    │        │   Violation detected
    │        │
    │        ├─> TradeFrequencyLimit rule
    │        │       │ Check trade count in window
    │        │       │ If exceeded → VIOLATION
    │        │       ▼
    │        │   Violation detected
    │        │
    │        └─> NoStopLossGrace rule
    │                │ Start grace timer
    │                │ Schedule stop loss check
    │                ▼
    │            Timer started
    │
    ├──> Logging Handler
    │        │ Log fill event
    │        ▼
    │    Event logged
    │
    └──> Enforcement Engine (if violations)
             │
             │ Prioritize violations
             ▼
         Execute highest priority action:
             │
             ├─> Close excess contracts
             ├─> Flatten account
             └─> Set lockout
             │
             ▼
         Send order to broker via SDK Adapter
             │
             ▼
         Wait for confirmation
             │
             ▼
         Update State Manager
             │
             ▼
         Send notification
             │
             ▼
         Log enforcement action
```

---

## 3. Position Update Event Flow (Price Movement)

```
Broker (TopstepX)
    │
    │ onPositionUpdate event (price changed)
    ▼
SDK Adapter
    │
    │ Extract mark price, unrealized PnL
    ▼
Event Bus
    │
    ├──> State Manager Handler
    │        │ Update position current_price
    │        │ Recalculate unrealized PnL
    │        ▼
    │    State updated
    │
    └──> Risk Engine Handler
             │
             │ Get current state
             ▼
         Evaluate per-trade unrealized rules:
             │
             ├─> UnrealizedLoss (per position)
             │       │ For each position:
             │       │   If unrealized < limit → VIOLATION
             │       ▼
             │   Position X violated
             │
             ├─> UnrealizedProfit (per position)
             │       │ For each position:
             │       │   If unrealized > limit → VIOLATION
             │       ▼
             │   Position Y violated
             │
             └─> Combined PnL Check:
                     │
                     │ realized_pnl = state.get_realized_pnl()
                     │ unrealized_pnl = sum(all positions' unrealized)
                     │ combined = realized + unrealized
                     │
                     ├─> DailyRealizedLoss
                     │       │ If combined <= loss_limit → VIOLATION
                     │       ▼
                     │   Flatten + Lockout
                     │
                     └─> DailyRealizedProfit
                             │ If combined >= profit_limit → VIOLATION
                             ▼
                         Flatten + Lockout
             │
             ▼
         Enforcement Engine executes actions
             │
             ▼
         Notifications + Logging
```

---

## 4. Position Close Event Flow

```
Position Closed (manual or via stop/target)
    │
    │ onPositionClose event
    ▼
SDK Adapter
    │
    │ Extract realized PnL
    ▼
Event Bus
    │
    ├──> State Manager Handler
    │        │ Remove position from open_positions
    │        │ Add realized_pnl to daily total
    │        │ Recalculate combined exposure
    │        ▼
    │    State updated
    │
    └──> Risk Engine Handler
             │
             │ Check if realized PnL triggers limits
             ▼
         Evaluate:
             │
             ├─> DailyRealizedLoss
             │       │ If realized_pnl <= limit → VIOLATION
             │       ▼
             │   Flatten + Lockout
             │
             ├─> DailyRealizedProfit
             │       │ If realized_pnl >= limit → VIOLATION
             │       ▼
             │   Flatten + Lockout
             │
             └─> CooldownAfterLoss
                     │ If realized_pnl from this close <= threshold
                     │   → Start cooldown timer
                     ▼
                 Cooldown started
             │
             ▼
         Enforcement + Notifications
```

---

## 5. Combined PnL Monitoring Decision Tree

```
                    Position Update Event
                            │
                            ▼
              ┌─────────────────────────┐
              │ Get Realized PnL Today  │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │ Calculate Total         │
              │ Unrealized PnL          │
              │ (sum all positions)     │
              └─────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │ Combined = Realized +   │
              │            Unrealized   │
              └─────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
    ┌───────────────────┐   ┌───────────────────┐
    │ Combined <=       │   │ Combined >=       │
    │ Daily Loss Limit? │   │ Daily Profit Limit?│
    └───────────────────┘   └───────────────────┘
                │                       │
        Yes ────┤                       ├──── Yes
                ▼                       ▼
    ┌───────────────────┐   ┌───────────────────┐
    │ FLATTEN ALL       │   │ FLATTEN ALL       │
    │ LOCKOUT UNTIL 5PM │   │ LOCKOUT UNTIL 5PM │
    │ (Daily Loss Hit)  │   │ (Daily Profit Hit)│
    └───────────────────┘   └───────────────────┘
                │                       │
                └───────────┬───────────┘
                            ▼
                ┌───────────────────────┐
                │ Send Notification     │
                │ Log Enforcement       │
                │ Update State          │
                └───────────────────────┘
                            │
                            ▼
                    Trading Locked Out
                  (Cannot open new positions)
```

---

## 6. Enforcement Action Priority Decision Tree

```
                Multiple Rules Violated
                            │
                            ▼
              ┌─────────────────────────┐
              │ Prioritize by Severity  │
              └─────────────────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
        ┌───────────┐ ┌─────────┐ ┌─────────┐
        │ Critical  │ │ Warning │ │  Info   │
        │ (P1)      │ │ (P2)    │ │  (P3)   │
        └───────────┘ └─────────┘ └─────────┘
                │
                ▼
        Priority 1 (Critical):
            │
            ├─> Daily Loss Limit → Flatten + Lockout
            ├─> Daily Profit Limit → Flatten + Lockout
            └─> Session Block → Flatten
                │
                ▼
        Execute P1 action (flattens all positions)
                │
                ▼
        Lower priority violations now moot
        (positions already closed)
                │
                ▼
        END


        If no P1 violations:
                │
                ▼
        Priority 2 (Warning):
            │
            ├─> Per-Trade Unrealized Loss → Close position
            ├─> Per-Trade Unrealized Profit → Close position
            └─> Max Contracts → Close excess
                │
                ▼
        Execute P2 actions
                │
                ▼
        END


        If no P1 or P2 violations:
                │
                ▼
        Priority 3 (Info):
            │
            ├─> Trade Frequency → Reject fill
            └─> No Stop Loss Grace → Close position
                │
                ▼
        Execute P3 actions
                │
                ▼
        END
```

---

## 7. Daily Reset Flow (5pm CT)

```
Background Timer (checks every minute)
    │
    ▼
┌─────────────────────────┐
│ Is current time >= 5pm? │
│ AND last_reset < 5pm?   │
└─────────────────────────┘
    │
    │ Yes
    ▼
For each account:
    │
    ├─> Reset realized_pnl_today to 0
    │
    ├─> Clear lockout_until (if daily lockout)
    │
    ├─> Reset trade frequency windows (daily windows)
    │
    ├─> Update last_daily_reset timestamp
    │
    └─> Persist state to disk
    │
    ▼
Log: "Daily reset completed for all accounts"
    │
    ▼
Send notification (optional): "Daily limits reset, good luck trading!"
```

---

## 8. State Persistence and Recovery Flow

```
Daemon Shutdown (Graceful)
    │
    ▼
┌─────────────────────────┐
│ Stop accepting events   │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Finish processing queue │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Persist state to disk   │
│ (all accounts)          │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Close SDK connection    │
└─────────────────────────┘
    │
    ▼
Exit cleanly


Daemon Startup (After Restart)
    │
    ▼
┌─────────────────────────┐
│ Load configuration      │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Load persisted state    │
│ from disk               │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Connect to broker       │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Query current positions │
│ from broker             │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Reconcile state:        │
│ - Add missed positions  │
│ - Remove stale positions│
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Start event loop        │
└─────────────────────────┘
    │
    ▼
Daemon ready
```

---

## 9. CLI Communication Flow

```
Trader CLI                          Daemon
    │                                   │
    │ (User selects "View Positions")  │
    │                                   │
    ▼                                   │
┌──────────────────┐                   │
│ Build IPC request│                   │
│ {cmd: "get_pos"} │                   │
└──────────────────┘                   │
    │                                   │
    │ Send via Named Pipe               │
    ├──────────────────────────────────>│
    │                                   │
    │                                   ▼
    │                       ┌────────────────────┐
    │                       │ Receive request    │
    │                       └────────────────────┘
    │                                   │
    │                                   ▼
    │                       ┌────────────────────┐
    │                       │ Query State Manager│
    │                       │ get_positions()    │
    │                       └────────────────────┘
    │                                   │
    │                                   ▼
    │                       ┌────────────────────┐
    │                       │ Build JSON response│
    │                       │ {positions: [...]} │
    │                       └────────────────────┘
    │                                   │
    │                  Send response    │
    │<──────────────────────────────────┤
    │                                   │
    ▼                                   │
┌──────────────────┐                   │
│ Parse response   │                   │
│ Display positions│                   │
└──────────────────┘                   │
    │                                   │
    ▼
User sees positions


Admin CLI (Stop Daemon)
    │
    │ (User selects "Stop Daemon")
    │
    ▼
┌──────────────────┐
│ Prompt password  │
└──────────────────┘
    │
    │ User enters password
    ▼
┌──────────────────┐
│ Hash password    │
└──────────────────┘
    │
    │ Send IPC request
    │ {cmd: "stop", auth: hash}
    ├──────────────────────────────────>
    │                                   │
    │                                   ▼
    │                       ┌────────────────────┐
    │                       │ Verify auth hash   │
    │                       └────────────────────┘
    │                                   │
    │                              Valid?
    │                                   │
    │                           Yes     │
    │                                   ▼
    │                       ┌────────────────────┐
    │                       │ Initiate shutdown  │
    │                       └────────────────────┘
    │                                   │
    │                  Ack response     │
    │<──────────────────────────────────┤
    │                                   │
    ▼                                   ▼
┌──────────────────┐         (Daemon shuts down)
│ "Daemon stopped" │
└──────────────────┘
```

---

## 10. Rule Evaluation Sequence Diagram

```
Event               Risk Engine          State Manager       Rule Plugin         Enforcement Engine
  │                      │                      │                  │                       │
  │  New fill event      │                      │                  │                       │
  ├─────────────────────>│                      │                  │                       │
  │                      │                      │                  │                       │
  │                      │ Get account state    │                  │                       │
  │                      ├─────────────────────>│                  │                       │
  │                      │                      │                  │                       │
  │                      │ Return state         │                  │                       │
  │                      │<─────────────────────┤                  │                       │
  │                      │                      │                  │                       │
  │                      │ Evaluate rule        │                  │                       │
  │                      ├─────────────────────────────────────────>│                       │
  │                      │                      │                  │                       │
  │                      │                      │  (Rule checks    │                       │
  │                      │                      │   event + state) │                       │
  │                      │                      │                  │                       │
  │                      │ Return violation     │                  │                       │
  │                      │<─────────────────────────────────────────┤                       │
  │                      │                      │                  │                       │
  │                      │ Get enforcement action                  │                       │
  │                      ├─────────────────────────────────────────>│                       │
  │                      │                      │                  │                       │
  │                      │ Return action        │                  │                       │
  │                      │<─────────────────────────────────────────┤                       │
  │                      │                      │                  │                       │
  │                      │ Execute action                          │                       │
  │                      ├────────────────────────────────────────────────────────────────>│
  │                      │                      │                  │                       │
  │                      │                      │                  │  (Send close order    │
  │                      │                      │                  │   to broker)          │
  │                      │                      │                  │                       │
  │                      │ Action completed                        │                       │
  │                      │<────────────────────────────────────────────────────────────────┤
  │                      │                      │                  │                       │
  │                      │ Update state         │                  │                       │
  │                      ├─────────────────────>│                  │                       │
  │                      │                      │                  │                       │
  │                      │ Confirmed            │                  │                       │
  │                      │<─────────────────────┤                  │                       │
  │                      │                      │                  │                       │
  │                      │ Log + Notify                            │                       │
  │                      ├──> (Logging & Notification Services)    │                       │
  │                      │                      │                  │                       │
```

---

## 11. Lockout State Machine

```
                        ┌───────────────┐
                        │    Normal     │
                        │   (Trading)   │
                        └───────────────┘
                                │
                                │ Daily limit hit
                                ▼
                        ┌───────────────┐
                        │  Locked Out   │
                        │ (Until 5pm CT)│
                        └───────────────┘
                                │
                        ┌───────┼───────┐
                        ▼               ▼
                Daily Reset      Admin Override
                (5pm CT)         (Force Unlock)
                        │               │
                        └───────┬───────┘
                                ▼
                        ┌───────────────┐
                        │    Normal     │
                        │   (Trading)   │
                        └───────────────┘


State Transitions:

Normal → Locked Out:
    - Trigger: DailyRealizedLoss exceeded
    - Trigger: DailyRealizedProfit exceeded
    - Action: Flatten all positions
    - Flag: lockout_until = 5pm CT today

Locked Out → Normal:
    - Trigger: Daily reset at 5pm CT
    - Action: Clear lockout_until flag
    - OR
    - Trigger: Admin force unlock (manual override)
    - Action: Clear lockout_until flag

While Locked Out:
    - All fill events → immediately closed
    - Positions cannot be opened
    - Existing positions can be managed (modify SL/TP, manual close)
```

---

## 12. Cooldown State Machine

```
                        ┌───────────────┐
                        │    Normal     │
                        └───────────────┘
                                │
                                │ Loss threshold hit
                                ▼
                        ┌───────────────┐
                        │   Cooldown    │
                        │  (X seconds)  │
                        └───────────────┘
                                │
                                │ Timer expires
                                ▼
                        ┌───────────────┐
                        │    Normal     │
                        └───────────────┘


State Transitions:

Normal → Cooldown:
    - Trigger: Position closed with loss >= threshold
    - Action: Set cooldown_until = now + duration
    - Flag: is_in_cooldown = true

Cooldown → Normal:
    - Trigger: Timer expires (cooldown_until <= now)
    - Action: Clear cooldown_until
    - Flag: is_in_cooldown = false

While in Cooldown:
    - New fills → rejected/closed
    - Cannot add to existing positions
    - Can modify SL/TP
    - Can manually close positions
```

---

## Summary

These diagrams illustrate:

1. **System Architecture**: Components and their relationships
2. **Event Flows**: How events propagate through the system
3. **Decision Trees**: How rules are evaluated and prioritized
4. **Sequence Diagrams**: Interactions between components
5. **State Machines**: Lockout and cooldown state transitions

**For Implementation Agent**: Use these diagrams as reference when:
- Building the event pipeline
- Implementing rule evaluation logic
- Designing enforcement prioritization
- Debugging event flow issues
- Understanding state transitions

These visual representations complement the detailed architecture docs and provide a higher-level view of system behavior.
