# IPC/API Layer Implementation

## Overview

This document provides detailed implementation specifications for the Inter-Process Communication (IPC) layer described in `08-daemon-service.md` and `06-cli-interfaces.md`. While the high-level architecture defines WHAT the IPC system does, this document specifies HOW to implement it with specific protocols, libraries, authentication mechanisms, and request/response formats.

**Implementation Status**: NOT IMPLEMENTED (P0 Priority)
**Dependencies**: Configuration System (16), Logging Framework (20)
**Estimated Effort**: 2 days

## Core Implementation Requirements

1. **Protocol**: HTTP/REST API (simple, testable, cross-platform)
2. **Library**: `FastAPI` for async HTTP server + `httpx` for client
3. **Transport**: localhost only (127.0.0.1:5555) for security
4. **Format**: JSON request/response with Pydantic validation
5. **Authentication**: HMAC-based challenge-response for admin commands
6. **Rate Limiting**: 100 requests/minute per client IP

---

## Architecture Design

### Communication Model

```
Admin CLI                    Trader CLI
    ↓                            ↓
    HTTP POST                    HTTP GET
    ↓                            ↓
127.0.0.1:5555 (Daemon HTTP API)
    ↓
DaemonAPIServer (FastAPI)
    ↓
RiskEngine / StateManager / ConfigManager
```

**Key Decisions**:
- HTTP/REST over Named Pipes: Cross-platform, easier testing, WSL compatible
- Localhost only: No external network access, secure by design
- Async FastAPI: Matches daemon's async architecture

---

## HTTP API Endpoints

### Public Endpoints (No Auth Required)

#### 1. GET /health
**Purpose**: Check daemon health and uptime

**Response**:
```json
{
  "status": "healthy",
  "uptime_seconds": 172800,
  "version": "1.0.0",
  "accounts": {
    "ABC123": {
      "connected": true,
      "last_event_seconds_ago": 2,
      "positions_count": 2,
      "lockout": false
    }
  },
  "memory_usage_mb": 245,
  "cpu_usage_percent": 1.2
}
```

#### 2. GET /status
**Purpose**: Get overall daemon status

**Response**:
```json
{
  "daemon_status": "running",
  "started_at": "2025-10-17T10:00:00Z",
  "config_loaded": true,
  "sdk_connected": true,
  "accounts_monitored": 1
}
```

---

### Account Query Endpoints (No Auth Required)

#### 3. GET /accounts/{account_id}/positions
**Purpose**: Get open positions for an account

**Response**:
```json
{
  "account_id": "ABC123",
  "positions": [
    {
      "symbol": "MNQ",
      "side": "long",
      "quantity": 2,
      "entry_price": 5042.50,
      "current_price": 5055.00,
      "unrealized_pnl": 62.50
    },
    {
      "symbol": "ES",
      "side": "long",
      "quantity": 1,
      "entry_price": 4502.25,
      "current_price": 4498.00,
      "unrealized_pnl": -21.25
    }
  ],
  "total_unrealized_pnl": 41.25
}
```

#### 4. GET /accounts/{account_id}/pnl
**Purpose**: Get realized and unrealized PnL

**Response**:
```json
{
  "account_id": "ABC123",
  "realized_pnl_today": -150.00,
  "unrealized_pnl": 41.25,
  "combined_pnl": -108.75,
  "daily_loss_limit": -500.00,
  "daily_profit_target": 1000.00,
  "lockout": false
}
```

#### 5. GET /accounts/{account_id}/enforcement
**Purpose**: Get recent enforcement actions

**Query Params**:
- `limit`: Number of actions to return (default: 20, max: 100)

**Response**:
```json
{
  "account_id": "ABC123",
  "enforcement_actions": [
    {
      "timestamp": "2025-10-17T14:23:45Z",
      "rule": "UnrealizedLoss",
      "action": "close_position",
      "position": {
        "symbol": "MNQ",
        "quantity": 2,
        "unrealized_pnl": -210.00
      },
      "result": "success"
    },
    {
      "timestamp": "2025-10-17T12:10:30Z",
      "rule": "MaxContracts",
      "action": "reduce_position",
      "position": {
        "symbol": "ES",
        "quantity": 1,
        "excess_contracts": 1
      },
      "result": "success"
    }
  ]
}
```

#### 6. GET /accounts/{account_id}/timers
**Purpose**: Get active timers (cooldowns, grace periods)

**Response**:
```json
{
  "account_id": "ABC123",
  "timers": {
    "daily_reset": {
      "next_reset_at": "2025-10-17T22:00:00Z",
      "seconds_remaining": 27315
    },
    "cooldown_expires_at": null,
    "stop_loss_grace_expires_at": null
  }
}
```

---

### Admin Endpoints (Auth Required)

#### 7. POST /admin/auth/challenge
**Purpose**: Request authentication challenge for admin commands

**Request**:
```json
{
  "username": "admin"
}
```

**Response**:
```json
{
  "challenge_id": "a7b3c9d2-1234-5678-9abc-def012345678",
  "nonce": "f3a8b9c1d2e4f5a6b7c8d9e0f1a2b3c4",
  "expires_at": "2025-10-17T14:25:00Z"
}
```

#### 8. POST /admin/auth/verify
**Purpose**: Verify authentication response

**Request**:
```json
{
  "challenge_id": "a7b3c9d2-1234-5678-9abc-def012345678",
  "response_hash": "sha256_hmac_of_nonce_and_password"
}
```

**Response**:
```json
{
  "authenticated": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-10-17T15:24:00Z"
}
```

#### 9. POST /admin/config/reload
**Purpose**: Hot-reload configuration files

**Headers**: `Authorization: Bearer <token>`

**Request**:
```json
{
  "config_type": "risk_rules"
}
```

**Response**:
```json
{
  "success": true,
  "config_type": "risk_rules",
  "reloaded_at": "2025-10-17T14:25:30Z",
  "message": "Risk rules configuration reloaded successfully"
}
```

#### 10. POST /admin/daemon/stop
**Purpose**: Gracefully shutdown daemon

**Headers**: `Authorization: Bearer <token>`

**Request**:
```json
{
  "reason": "Manual shutdown for maintenance"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Daemon shutdown initiated",
  "shutdown_eta_seconds": 30
}
```

---

## Python Implementation

### API Server (src/api/server.py)

```python
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import secrets
import hmac
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass
import uvicorn


app = FastAPI(
    title="Risk Manager Daemon API",
    version="1.0.0",
    description="IPC API for Admin and Trader CLI interfaces"
)


# ============================================================================
# Request/Response Models
# ============================================================================

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    version: str
    accounts: Dict[str, Dict[str, Any]]
    memory_usage_mb: float
    cpu_usage_percent: float


class Position(BaseModel):
    symbol: str
    side: str  # "long" or "short"
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float


class PositionsResponse(BaseModel):
    account_id: str
    positions: List[Position]
    total_unrealized_pnl: float


class PnLResponse(BaseModel):
    account_id: str
    realized_pnl_today: float
    unrealized_pnl: float
    combined_pnl: float
    daily_loss_limit: float
    daily_profit_target: float
    lockout: bool


class EnforcementAction(BaseModel):
    timestamp: datetime
    rule: str
    action: str
    position: Dict[str, Any]
    result: str


class EnforcementResponse(BaseModel):
    account_id: str
    enforcement_actions: List[EnforcementAction]


class AuthChallengeRequest(BaseModel):
    username: str


class AuthChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    expires_at: datetime


class AuthVerifyRequest(BaseModel):
    challenge_id: str
    response_hash: str


class AuthVerifyResponse(BaseModel):
    authenticated: bool
    token: Optional[str] = None
    expires_at: Optional[datetime] = None


class ConfigReloadRequest(BaseModel):
    config_type: str = Field(..., description="Type of config: system, accounts, risk_rules, notifications")


class ConfigReloadResponse(BaseModel):
    success: bool
    config_type: str
    reloaded_at: datetime
    message: str


# ============================================================================
# Authentication System
# ============================================================================

@dataclass
class AuthChallenge:
    """Active authentication challenge."""
    challenge_id: str
    nonce: str
    created_at: datetime
    expires_at: datetime


class AuthManager:
    """Manages admin authentication challenges and tokens."""

    def __init__(self, password_hash: str):
        self.password_hash = password_hash
        self.active_challenges: Dict[str, AuthChallenge] = {}
        self.active_tokens: Dict[str, datetime] = {}

    def create_challenge(self) -> AuthChallenge:
        """Create new authentication challenge."""
        challenge_id = secrets.token_urlsafe(32)
        nonce = secrets.token_hex(32)
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(minutes=5)

        challenge = AuthChallenge(
            challenge_id=challenge_id,
            nonce=nonce,
            created_at=created_at,
            expires_at=expires_at
        )

        self.active_challenges[challenge_id] = challenge
        return challenge

    def verify_challenge(self, challenge_id: str, response_hash: str, password: str) -> Optional[str]:
        """
        Verify challenge response and issue token if valid.

        Expected response_hash: HMAC-SHA256(nonce, password)
        """
        challenge = self.active_challenges.get(challenge_id)

        if not challenge:
            return None

        # Check expiration
        if datetime.utcnow() > challenge.expires_at:
            del self.active_challenges[challenge_id]
            return None

        # Compute expected hash
        expected_hash = hmac.new(
            password.encode(),
            challenge.nonce.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify hash
        if not secrets.compare_digest(response_hash, expected_hash):
            return None

        # Clean up challenge
        del self.active_challenges[challenge_id]

        # Issue token
        token = secrets.token_urlsafe(48)
        self.active_tokens[token] = datetime.utcnow() + timedelta(hours=1)

        return token

    def verify_token(self, token: str) -> bool:
        """Verify admin token is valid and not expired."""
        if token not in self.active_tokens:
            return False

        # Check expiration
        if datetime.utcnow() > self.active_tokens[token]:
            del self.active_tokens[token]
            return False

        return True


# ============================================================================
# Dependency Injection
# ============================================================================

# Global references (injected at startup)
risk_engine = None
state_manager = None
config_manager = None
logger_manager = None
auth_manager = None


def get_auth_manager() -> AuthManager:
    """Dependency: Get auth manager."""
    if auth_manager is None:
        raise HTTPException(status_code=500, detail="Auth manager not initialized")
    return auth_manager


def verify_admin_token(authorization: Optional[str] = Header(None)):
    """Dependency: Verify admin authentication token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ")[1]

    if not auth_manager.verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return token


# ============================================================================
# Public Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Get daemon health status."""
    import psutil
    import os

    process = psutil.Process(os.getpid())

    accounts_status = {}
    for account_id in state_manager.get_all_account_ids():
        state = state_manager.get_account_state(account_id)
        accounts_status[account_id] = {
            "connected": True,  # TODO: Get from connection manager
            "last_event_seconds_ago": 2,  # TODO: Track last event time
            "positions_count": len(state.positions),
            "lockout": state.lockout_until is not None
        }

    return HealthResponse(
        status="healthy",
        uptime_seconds=int(process.create_time()),
        version="1.0.0",
        accounts=accounts_status,
        memory_usage_mb=process.memory_info().rss / 1024 / 1024,
        cpu_usage_percent=process.cpu_percent(interval=0.1)
    )


@app.get("/accounts/{account_id}/positions", response_model=PositionsResponse)
async def get_positions(account_id: str):
    """Get open positions for account."""
    state = state_manager.get_account_state(account_id)

    if state is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    positions = []
    total_unrealized = 0.0

    for pos in state.positions:
        positions.append(Position(
            symbol=pos.symbol,
            side=pos.side,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            current_price=pos.current_price,
            unrealized_pnl=pos.unrealized_pnl
        ))
        total_unrealized += pos.unrealized_pnl

    return PositionsResponse(
        account_id=account_id,
        positions=positions,
        total_unrealized_pnl=total_unrealized
    )


@app.get("/accounts/{account_id}/pnl", response_model=PnLResponse)
async def get_pnl(account_id: str):
    """Get PnL summary for account."""
    state = state_manager.get_account_state(account_id)

    if state is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Get risk limits from config
    rules = config_manager.get_rules_for_account(account_id)
    daily_loss_limit = -500.00  # Default
    daily_profit_target = 1000.00  # Default

    for rule in rules:
        if rule.rule == "DailyRealizedLoss":
            daily_loss_limit = rule.params.get("limit", daily_loss_limit)
        elif rule.rule == "DailyRealizedProfit":
            daily_profit_target = rule.params.get("target", daily_profit_target)

    return PnLResponse(
        account_id=account_id,
        realized_pnl_today=state.realized_pnl_today,
        unrealized_pnl=state.unrealized_pnl,
        combined_pnl=state.realized_pnl_today + state.unrealized_pnl,
        daily_loss_limit=daily_loss_limit,
        daily_profit_target=daily_profit_target,
        lockout=state.lockout_until is not None
    )


@app.get("/accounts/{account_id}/enforcement", response_model=EnforcementResponse)
async def get_enforcement_log(account_id: str, limit: int = 20):
    """Get recent enforcement actions."""
    if limit > 100:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 100")

    # Query enforcement actions from state or log
    actions = state_manager.get_enforcement_history(account_id, limit=limit)

    return EnforcementResponse(
        account_id=account_id,
        enforcement_actions=actions
    )


# ============================================================================
# Admin Authentication Endpoints
# ============================================================================

@app.post("/admin/auth/challenge", response_model=AuthChallengeResponse)
async def request_auth_challenge(request: AuthChallengeRequest):
    """Request authentication challenge."""
    if request.username != "admin":
        raise HTTPException(status_code=404, detail="User not found")

    challenge = auth_manager.create_challenge()

    return AuthChallengeResponse(
        challenge_id=challenge.challenge_id,
        nonce=challenge.nonce,
        expires_at=challenge.expires_at
    )


@app.post("/admin/auth/verify", response_model=AuthVerifyResponse)
async def verify_auth_response(request: AuthVerifyRequest):
    """Verify authentication response and issue token."""
    # Get password from config
    admin_config = config_manager.get_system_config().admin
    password = admin_config.password_hash  # TODO: This should be verified properly

    token = auth_manager.verify_challenge(
        request.challenge_id,
        request.response_hash,
        password
    )

    if not token:
        return AuthVerifyResponse(authenticated=False)

    return AuthVerifyResponse(
        authenticated=True,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )


# ============================================================================
# Admin Control Endpoints
# ============================================================================

@app.post("/admin/config/reload", response_model=ConfigReloadResponse, dependencies=[Depends(verify_admin_token)])
async def reload_config(request: ConfigReloadRequest):
    """Hot-reload configuration file."""
    try:
        config_manager.reload_config(f"{request.config_type}.json")

        logger_manager.log_audit(
            action="config_reload",
            actor="admin",
            details={"config_type": request.config_type}
        )

        return ConfigReloadResponse(
            success=True,
            config_type=request.config_type,
            reloaded_at=datetime.utcnow(),
            message=f"{request.config_type} configuration reloaded successfully"
        )

    except Exception as e:
        logger_manager.log_error(f"Failed to reload config: {e}", exception=e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/daemon/stop", dependencies=[Depends(verify_admin_token)])
async def stop_daemon(reason: Optional[str] = None):
    """Gracefully shutdown daemon."""
    logger_manager.log_audit(
        action="daemon_shutdown",
        actor="admin",
        details={"reason": reason or "Manual shutdown"}
    )

    # Trigger graceful shutdown
    # TODO: Implement shutdown signal

    return {
        "success": True,
        "message": "Daemon shutdown initiated",
        "shutdown_eta_seconds": 30
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected errors."""
    logger_manager.log_error(f"API error: {exc}", exception=exc)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ============================================================================
# Server Initialization
# ============================================================================

def initialize_api_server(
    _risk_engine,
    _state_manager,
    _config_manager,
    _logger_manager,
    _auth_manager
):
    """Initialize API server with dependencies."""
    global risk_engine, state_manager, config_manager, logger_manager, auth_manager

    risk_engine = _risk_engine
    state_manager = _state_manager
    config_manager = _config_manager
    logger_manager = _logger_manager
    auth_manager = _auth_manager


def start_api_server(host: str = "127.0.0.1", port: int = 5555):
    """Start the API server."""
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False  # Use our own logging
    )
```

---

## Client Library (src/api/client.py)

```python
import httpx
from typing import Optional, Dict, Any, List
import hmac
import hashlib


class DaemonAPIClient:
    """Client library for communicating with Risk Manager Daemon API."""

    def __init__(self, base_url: str = "http://127.0.0.1:5555", timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.Client(base_url=base_url, timeout=timeout)
        self.auth_token: Optional[str] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close client connection."""
        self.client.close()

    # Public endpoints

    def get_health(self) -> Dict[str, Any]:
        """Get daemon health status."""
        response = self.client.get("/health")
        response.raise_for_status()
        return response.json()

    def get_positions(self, account_id: str) -> Dict[str, Any]:
        """Get open positions for account."""
        response = self.client.get(f"/accounts/{account_id}/positions")
        response.raise_for_status()
        return response.json()

    def get_pnl(self, account_id: str) -> Dict[str, Any]:
        """Get PnL summary for account."""
        response = self.client.get(f"/accounts/{account_id}/pnl")
        response.raise_for_status()
        return response.json()

    def get_enforcement_log(self, account_id: str, limit: int = 20) -> Dict[str, Any]:
        """Get recent enforcement actions."""
        response = self.client.get(f"/accounts/{account_id}/enforcement?limit={limit}")
        response.raise_for_status()
        return response.json()

    # Admin authentication

    def authenticate_admin(self, password: str) -> bool:
        """Authenticate as admin and obtain token."""
        # Request challenge
        challenge_response = self.client.post(
            "/admin/auth/challenge",
            json={"username": "admin"}
        )
        challenge_response.raise_for_status()
        challenge_data = challenge_response.json()

        # Compute response hash
        nonce = challenge_data["nonce"]
        response_hash = hmac.new(
            password.encode(),
            nonce.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify challenge
        verify_response = self.client.post(
            "/admin/auth/verify",
            json={
                "challenge_id": challenge_data["challenge_id"],
                "response_hash": response_hash
            }
        )
        verify_response.raise_for_status()
        verify_data = verify_response.json()

        if verify_data["authenticated"]:
            self.auth_token = verify_data["token"]
            return True

        return False

    def _admin_headers(self) -> Dict[str, str]:
        """Get headers for admin requests."""
        if not self.auth_token:
            raise ValueError("Not authenticated. Call authenticate_admin() first.")

        return {"Authorization": f"Bearer {self.auth_token}"}

    # Admin endpoints

    def reload_config(self, config_type: str) -> Dict[str, Any]:
        """Hot-reload configuration file."""
        response = self.client.post(
            "/admin/config/reload",
            json={"config_type": config_type},
            headers=self._admin_headers()
        )
        response.raise_for_status()
        return response.json()

    def stop_daemon(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """Gracefully shutdown daemon."""
        response = self.client.post(
            "/admin/daemon/stop",
            json={"reason": reason},
            headers=self._admin_headers()
        )
        response.raise_for_status()
        return response.json()
```

---

## Testing Strategy

### Unit Tests

```python
import unittest
from fastapi.testclient import TestClient
from unittest.mock import Mock


class TestDaemonAPI(unittest.TestCase):

    def setUp(self):
        """Set up test client."""
        # Mock dependencies
        global risk_engine, state_manager, config_manager, logger_manager, auth_manager

        state_manager = Mock()
        config_manager = Mock()
        logger_manager = Mock()
        auth_manager = AuthManager(password_hash="test_hash")

        self.client = TestClient(app)

    def test_health_endpoint(self):
        """Test health endpoint returns valid response."""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("uptime_seconds", data)

    def test_auth_challenge_flow(self):
        """Test admin authentication flow."""
        # Request challenge
        challenge_response = self.client.post(
            "/admin/auth/challenge",
            json={"username": "admin"}
        )
        self.assertEqual(challenge_response.status_code, 200)
        challenge_data = challenge_response.json()

        self.assertIn("challenge_id", challenge_data)
        self.assertIn("nonce", challenge_data)

        # Compute response hash
        nonce = challenge_data["nonce"]
        password = "test_password"
        response_hash = hmac.new(password.encode(), nonce.encode(), hashlib.sha256).hexdigest()

        # Verify challenge
        verify_response = self.client.post(
            "/admin/auth/verify",
            json={
                "challenge_id": challenge_data["challenge_id"],
                "response_hash": response_hash
            }
        )
        self.assertEqual(verify_response.status_code, 200)

    def test_unauthorized_admin_access(self):
        """Test admin endpoints reject requests without auth."""
        response = self.client.post("/admin/config/reload", json={"config_type": "risk_rules"})

        self.assertEqual(response.status_code, 401)
```

### Integration Tests

```python
def test_cli_client_integration():
    """Test CLI client can communicate with daemon."""
    # Start daemon API server in background
    # ...

    # Use client library
    with DaemonAPIClient() as client:
        # Test health check
        health = client.get_health()
        assert health["status"] == "healthy"

        # Test authentication
        authenticated = client.authenticate_admin("admin_password")
        assert authenticated

        # Test admin command
        result = client.reload_config("risk_rules")
        assert result["success"]
```

---

## Rate Limiting

```python
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/accounts/{account_id}/positions")
@limiter.limit("100/minute")
async def get_positions(request: Request, account_id: str):
    # ... endpoint implementation
    pass
```

---

## Summary for Implementation Agent

**To implement IPC/API Layer, you must:**

1. **Install dependencies**:
   ```
   fastapi>=0.100
   uvicorn[standard]>=0.23
   httpx>=0.24
   pydantic>=2.0
   python-multipart>=0.0.6
   slowapi>=0.1.9  # Rate limiting
   psutil>=5.9  # Process metrics
   ```

2. **Create FastAPI server** in `src/api/server.py` with:
   - Public endpoints (health, positions, PnL, enforcement log)
   - Admin authentication (challenge-response HMAC)
   - Admin control endpoints (reload config, stop daemon)
   - Rate limiting (100 req/min)

3. **Create client library** in `src/api/client.py` for CLI usage

4. **Integrate with daemon startup** (start API server in background thread)

5. **Write unit tests** for endpoints and authentication

6. **Write integration tests** for CLI ↔ daemon communication

7. **Document API** (OpenAPI/Swagger auto-generated by FastAPI)

8. **Test from WSL** (ensure WSL CLI can reach Windows daemon)

**Critical Implementation Notes:**
- Bind to 127.0.0.1 ONLY (never 0.0.0.0) for security
- Use secrets module for nonces and tokens (cryptographically secure)
- Validate all inputs with Pydantic models
- Log all admin actions to audit log
- Implement proper error handling (don't leak internal errors)

**Dependencies**: Configuration (16), Logging (20)
**Blocks**: Admin CLI (18), Trader CLI
**Priority**: P0 (required for CLI interfaces)
