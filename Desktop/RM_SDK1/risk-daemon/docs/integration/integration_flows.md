# Integration Flows

## Overview

This document provides sequence diagrams and flow charts for key integration scenarios between the Risk Manager Daemon and project-x-py SDK.

---

## Flow 1: Daemon Startup and Connection

```
┌─────────────┐        ┌──────────────┐        ┌───────────┐        ┌──────────┐
│ Risk Daemon │        │  SDKAdapter  │        │ ProjectX  │        │ TopstepX │
│   (Main)    │        │              │        │    SDK    │        │  Broker  │
└──────┬──────┘        └──────┬───────┘        └─────┬─────┘        └────┬─────┘
       │                      │                      │                   │
       │ 1. load_config()     │                      │                   │
       ├──────────────────────┤                      │                   │
       │                      │                      │                   │
       │ 2. connect(account)  │                      │                   │
       ├─────────────────────>│                      │                   │
       │                      │                      │                   │
       │                      │ 3. TradingSuite.create()                 │
       │                      ├─────────────────────>│                   │
       │                      │                      │                   │
       │                      │                      │ 4. authenticate() │
       │                      │                      ├──────────────────>│
       │                      │                      │                   │
       │                      │                      │ 5. JWT token      │
       │                      │                      │<──────────────────┤
       │                      │                      │                   │
       │                      │                      │ 6. connect        │
       │                      │                      │    WebSockets     │
       │                      │                      ├──────────────────>│
       │                      │                      │                   │
       │                      │                      │ 7. CONNECTED evt  │
       │                      │                      │<──────────────────┤
       │                      │                      │                   │
       │                      │ 8. suite ready       │                   │
       │                      │<─────────────────────┤                   │
       │                      │                      │                   │
       │ 9. connection OK     │                      │                   │
       │<─────────────────────┤                      │                   │
       │                      │                      │                   │
       │ 10. register_event_handlers()               │                   │
       ├─────────────────────>│                      │                   │
       │                      │                      │                   │
       │                      │ 11. suite.on(ORDER_FILLED, handler)     │
       │                      ├─────────────────────>│                   │
       │                      │                      │                   │
       │ 12. daemon READY     │                      │                   │
       │                      │                      │                   │
```

**Key Points**:
1. SDK handles authentication automatically (JWT tokens)
2. WebSocket connections established to UserHub and MarketHub
3. Event handlers registered before trading begins
4. Daemon waits for CONNECTED event before proceeding

---

## Flow 2: Fill Event → Enforcement (Post-Trade Rejection)

```
┌──────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐   ┌──────────────┐
│ TopstepX │   │ProjectX  │   │Event       │   │Risk       │   │State         │   │Enforcement   │
│ Broker   │   │SDK       │   │Normalizer  │   │Handler    │   │Manager       │   │Engine        │
└────┬─────┘   └────┬─────┘   └─────┬──────┘   └─────┬─────┘   └──────┬───────┘   └──────┬───────┘
     │              │               │                │                │                  │
     │ 1. Order     │               │                │                │                  │
     │    Filled    │               │                │                │                  │
     ├─────────────>│               │                │                │                  │
     │              │               │                │                │                  │
     │              │ 2. SDK evt    │                │                │                  │
     │              │ ORDER_FILLED  │                │                │                  │
     │              ├──────────────>│                │                │                  │
     │              │               │                │                │                  │
     │              │               │ 3. normalize() │                │                  │
     │              │               │    to FILL evt │                │                  │
     │              │               ├───────────────>│                │                  │
     │              │               │                │                │                  │
     │              │               │                │ 4. get_state() │                  │
     │              │               │                ├───────────────>│                  │
     │              │               │                │                │                  │
     │              │               │                │ 5. AccountState│                  │
     │              │               │                │<───────────────┤                  │
     │              │               │                │                │                  │
     │              │               │                │ 6. evaluate_   │                  │
     │              │               │                │    all_rules() │                  │
     │              │               │                ├────────────────┤                  │
     │              │               │                │                │                  │
     │              │               │                │ 7. VIOLATION   │                  │
     │              │               │                │    detected    │                  │
     │              │               │                ├───────────────────────────────────>│
     │              │               │                │                │                  │
     │              │               │                │                │ 8. close_        │
     │              │               │                │                │    position()    │
     │              │<──────────────┼────────────────┼────────────────┼──────────────────┤
     │              │               │                │                │                  │
     │ 9. Close     │               │                │                │                  │
     │    Order     │               │                │                │                  │
     │<─────────────┤               │                │                │                  │
     │              │               │                │                │                  │
     │ 10. Filled   │               │                │                │                  │
     │──────────────>│               │                │                │                  │
     │              │               │                │                │                  │
     │              │ 11. ORDER_    │                │                │                  │
     │              │     FILLED    │                │                │                  │
     │              ├──────────────>│                │                │                  │
     │              │               │                │                │                  │
     │              │               │ 12. FILL evt   │                │ 13. log_         │
     │              │               │    (close)     │                │     enforcement()│
     │              │               ├───────────────>│                ├─────────────────>│
     │              │               │                │                │                  │
```

**Timing**:
- Step 1-7: ~50-100ms (event propagation + rule eval)
- Step 8-10: ~50-200ms (order placement + execution)
- **Total: 100-300ms** (95th percentile <500ms)

**Key Points**:
1. Cannot prevent initial fill (post-trade only)
2. Rule evaluation must be <10ms to minimize latency
3. Market orders ensure fast close execution
4. All steps logged for audit trail

---

## Flow 3: Position Update → PnL Monitoring

```
┌──────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐
│ TopstepX │   │ProjectX  │   │Event       │   │Price      │   │Risk          │
│ Market   │   │SDK       │   │Normalizer  │   │Cache      │   │Handler       │
└────┬─────┘   └────┬─────┘   └─────┬──────┘   └─────┬─────┘   └──────┬───────┘
     │              │               │                │                │
     │ 1. Quote     │               │                │                │
     │    Update    │               │                │                │
     ├─────────────>│               │                │                │
     │              │               │                │                │
     │              │ 2. QUOTE_     │                │                │
     │              │    UPDATE evt │                │                │
     │              ├──────────────>│                │                │
     │              │               │                │                │
     │              │               │ 3. update_     │                │
     │              │               │    cache()     │                │
     │              │               ├───────────────>│                │
     │              │               │                │                │
     │              │               │                │ (cache updated)│
     │              │               │                │                │
     │ 4. Position  │               │                │                │
     │    Updated   │               │                │                │
     ├─────────────>│               │                │                │
     │              │               │                │                │
     │              │ 5. POSITION_  │                │                │
     │              │    UPDATED    │                │                │
     │              ├──────────────>│                │                │
     │              │               │                │                │
     │              │               │ 6. get_price() │                │
     │              │               ├───────────────>│                │
     │              │               │                │                │
     │              │               │ 7. current_    │                │
     │              │               │    price       │                │
     │              │               │<───────────────┤                │
     │              │               │                │                │
     │              │               │ 8. calculate_  │                │
     │              │               │    unrealized_ │                │
     │              │               │    pnl()       │                │
     │              │               ├────────────────┤                │
     │              │               │                │                │
     │              │               │ 9. POSITION_   │                │
     │              │               │    UPDATE evt  │                │
     │              │               │    (with PnL)  │                │
     │              │               ├───────────────────────────────>│
     │              │               │                │                │
     │              │               │                │ 10. evaluate_  │
     │              │               │                │     PnL_rules()│
     │              │               │                │                │
```

**Key Points**:
1. Quote updates maintain price cache (no internal event)
2. Position updates trigger PnL recalculation
3. Unrealized PnL computed from cached price + tick value
4. Daily combined limit = realized + unrealized (checked on each update)

---

## Flow 4: State Reconciliation After Disconnect

```
┌──────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐
│ TopstepX │   │ProjectX  │   │Connection  │   │State      │   │Risk          │
│ Broker   │   │SDK       │   │Monitor     │   │Reconciler │   │Handler       │
└────┬─────┘   └────┬─────┘   └─────┬──────┘   └─────┬─────┘   └──────┬───────┘
     │              │               │                │                │
     │              │ 1. disconnect │                │                │
     │              │    detected   │                │                │
     │              ├──────────────>│                │                │
     │              │               │                │                │
     │              │               │ 2. DISCONNECTED│                │
     │              │               │    event       │                │
     │              │               ├───────────────────────────────>│
     │              │               │                │                │
     │              │               │                │ (log warning)  │
     │              │               │                │                │
     │              │ 3. auto-      │                │                │
     │              │    reconnect  │                │                │
     │<─────────────┤               │                │                │
     │              │               │                │                │
     │ 4. reconnect │               │                │                │
     │    success   │               │                │                │
     │──────────────>│               │                │                │
     │              │               │                │                │
     │              │ 5. CONNECTED  │                │                │
     │              │    event      │                │                │
     │              ├──────────────>│                │                │
     │              │               │                │                │
     │              │               │ 6. trigger_    │                │
     │              │               │    reconcile() │                │
     │              │               ├───────────────>│                │
     │              │               │                │                │
     │              │               │                │ 7. query_REST_ │
     │              │               │                │    positions() │
     │              │<──────────────┼────────────────┤                │
     │              │               │                │                │
     │ 8. current   │               │                │                │
     │    positions │               │                │                │
     │──────────────>│               │                │                │
     │              │               │                │                │
     │              │               │                │ 9. compare_    │
     │              │               │                │    with_cache()│
     │              │               │                │                │
     │              │               │                │ (discrepancies │
     │              │               │                │  detected)     │
     │              │               │                │                │
     │              │               │                │ 10. update_    │
     │              │               │                │     state()    │
     │              │               │                │                │
     │              │               │                │ 11. re_evaluate│
     │              │               │                │     _all_rules()
     │              │               │                ├───────────────>│
     │              │               │                │                │
```

**Reconciliation Steps**:
1. Detect reconnection (CONNECTED event after DISCONNECTED)
2. Query current positions via REST API
3. Compare with cached state
4. Log discrepancies (positions opened/closed during disconnect)
5. Update state to match broker
6. Re-evaluate all rules with reconciled state

**Expected Time**: <5 seconds

---

## Flow 5: Daily Reset (5pm CT)

```
┌──────────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐
│ Session      │   │Event       │   │State      │   │Risk          │
│ Timer        │   │Bus         │   │Manager    │   │Handler       │
└──────┬───────┘   └─────┬──────┘   └─────┬─────┘   └──────┬───────┘
       │                 │                │                │
       │ (every 1 sec)   │                │                │
       │                 │                │                │
       │ 1. check time   │                │                │
       │    = 5pm CT?    │                │                │
       ├─────────────────┤                │                │
       │                 │                │                │
       │ 2. YES → emit   │                │                │
       │    SESSION_TICK │                │                │
       ├────────────────>│                │                │
       │                 │                │                │
       │                 │ 3. SESSION_   │                │
       │                 │    TICK evt    │                │
       │                 │    (daily_rst) │                │
       │                 ├───────────────>│                │
       │                 │                │                │
       │                 │                │ 4. reset_      │
       │                 │                │    realized_   │
       │                 │                │    pnl()       │
       │                 │                │                │
       │                 │                │ (PnL = $0)     │
       │                 │                │                │
       │                 │                │ 5. reset_      │
       │                 │                │    frequency_  │
       │                 │                │    windows()   │
       │                 │                │                │
       │                 │                │ 6. clear_      │
       │                 │                │    lockouts()  │
       │                 │                │                │
       │                 │                │ (if configured)│
       │                 │                │                │
       │                 │                │ 7. log reset   │
       │                 │                │                │
       │ 8. sleep 60s    │                │                │
       │    (prevent     │                │                │
       │     duplicate)  │                │                │
       │                 │                │                │
```

**Reset Actions**:
1. Realized PnL → $0.00
2. Trade frequency windows reset
3. Lockouts cleared (optional, configurable)
4. Cooldowns cleared (optional, configurable)

**Timing**: Exactly at 17:00:00 CT (±5 seconds)

**DST Handling**: pytz.timezone("America/Chicago") handles DST automatically

---

## Summary: Critical Paths

| Flow | Latency Target | Critical For |
|------|---------------|-------------|
| Fill → Enforcement | <500ms (P95) | Per-trade limits |
| Quote → PnL Update | <100ms | Daily limits |
| Reconnect → Reconcile | <5s | State accuracy |
| Daily Reset | ±5s of 5pm CT | Daily limits reset |

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-15
**Author**: RM-SDK-Analyst
**Approved By**: [Pending Product Owner Review]
