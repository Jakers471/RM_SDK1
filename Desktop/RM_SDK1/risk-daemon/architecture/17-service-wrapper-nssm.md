# Windows Service Wrapper Implementation (NSSM)

## Overview

This document provides detailed implementation specifications for wrapping the Risk Manager Daemon as a Windows service using NSSM (Non-Sucking Service Manager). This builds on the concepts in `08-daemon-service.md` with specific technical implementation details.

**Implementation Status**: NOT IMPLEMENTED (P0 Priority)
**Dependencies**: Configuration System (16)
**Estimated Effort**: 2-3 days

## Why NSSM?

**NSSM Advantages**:
- No code changes required (wraps any executable)
- Built-in process monitoring and restart
- Easy installation/uninstallation
- Handles service lifecycle automatically
- Logs stdout/stderr to files
- Free and open-source

**Alternative Considered**: pywin32 (requires Python-specific service code)

---

## NSSM Installation

### Download and Setup

```powershell
# Download NSSM (version 2.24 or later)
# From: https://nssm.cc/download

# Extract to C:\Program Files\nssm\
# Add to system PATH
$env:Path += ";C:\Program Files\nssm\win64"
```

### Verify Installation

```powershell
nssm version
# Output: NSSM 2.24 64-bit 2014-08-31
```

---

## Service Installation Script

### Python Installation Script

**File**: `scripts/install_service.py`

```python
#!/usr/bin/env python3
"""
Install Risk Manager Daemon as Windows service using NSSM.

Usage:
    python install_service.py
"""

import os
import subprocess
import sys
from pathlib import Path

# Service configuration
SERVICE_NAME = "RiskManagerDaemon"
SERVICE_DISPLAY_NAME = "Risk Manager Daemon"
SERVICE_DESCRIPTION = "Professional risk management service for trading accounts"

def check_admin_privileges():
    """Verify script is run with administrator privileges."""
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        is_admin = False

    if not is_admin:
        print("ERROR: This script must be run as Administrator")
        print("Right-click and select 'Run as administrator'")
        sys.exit(1)

def find_nssm():
    """Locate nssm.exe in system PATH."""
    nssm_path = shutil.which("nssm")
    if not nssm_path:
        print("ERROR: NSSM not found in PATH")
        print("Download from: https://nssm.cc/download")
        print("Extract to C:\\Program Files\\nssm\\ and add to PATH")
        sys.exit(1)
    return nssm_path

def get_python_executable():
    """Get full path to Python interpreter."""
    return sys.executable

def get_daemon_script():
    """Get full path to daemon entry point script."""
    # Assuming daemon entry point is src/main.py
    project_root = Path(__file__).parent.parent
    daemon_script = project_root / "src" / "main.py"

    if not daemon_script.exists():
        print(f"ERROR: Daemon script not found: {daemon_script}")
        sys.exit(1)

    return str(daemon_script.resolve())

def install_service():
    """Install Risk Manager Daemon as Windows service."""
    nssm = find_nssm()
    python_exe = get_python_executable()
    daemon_script = get_daemon_script()

    print(f"Installing {SERVICE_NAME} as Windows service...")
    print(f"Python: {python_exe}")
    print(f"Daemon: {daemon_script}")

    # Install service
    result = subprocess.run([
        nssm, "install", SERVICE_NAME,
        python_exe, daemon_script
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: Failed to install service: {result.stderr}")
        sys.exit(1)

    print(f"Service {SERVICE_NAME} installed successfully")

    # Configure service
    configure_service(nssm)

def configure_service(nssm):
    """Configure service parameters."""
    configs = [
        # Display name
        ("set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY_NAME),

        # Description
        ("set", SERVICE_NAME, "Description", SERVICE_DESCRIPTION),

        # Start type: Automatic (delayed)
        ("set", SERVICE_NAME, "Start", "SERVICE_DELAYED_AUTO_START"),

        # Dependencies: Network service
        ("set", SERVICE_NAME, "DependOnService", "Tcpip"),

        # Restart on failure
        ("set", SERVICE_NAME, "AppExit", "Default", "Restart"),

        # Restart delays (10s, 30s, 60s)
        ("set", SERVICE_NAME, "AppRestartDelay", "10000"),  # First failure: 10s

        # Throttle restarts (max 3 per 5 minutes)
        ("set", SERVICE_NAME, "AppThrottle", "300000"),  # 5 minutes

        # Stdout/stderr logging
        ("set", SERVICE_NAME, "AppStdout", os.path.expanduser("~/.risk_manager/logs/service_stdout.log")),
        ("set", SERVICE_NAME, "AppStderr", os.path.expanduser("~/.risk_manager/logs/service_stderr.log")),

        # Log rotation (10 MB per file, keep 5 files)
        ("set", SERVICE_NAME, "AppRotateFiles", "1"),
        ("set", SERVICE_NAME, "AppRotateBytes", "10485760"),  # 10 MB
        ("set", SERVICE_NAME, "AppRotateOnline", "1"),

        # Shutdown timeout (30 seconds for graceful shutdown)
        ("set", SERVICE_NAME, "AppStopMethodConsole", "30000"),
        ("set", SERVICE_NAME, "AppStopMethodWindow", "30000"),
    ]

    for config in configs:
        result = subprocess.run([nssm, *config], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"WARNING: Failed to set {config[2]}: {result.stderr}")

    print("Service configured successfully")

def start_service():
    """Start the service after installation."""
    result = subprocess.run(["sc", "start", SERVICE_NAME], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Service {SERVICE_NAME} started successfully")
    else:
        print(f"Service installed but not started. Start manually with:")
        print(f"  sc start {SERVICE_NAME}")

def main():
    print("=" * 60)
    print("Risk Manager Daemon - Service Installation")
    print("=" * 60)

    check_admin_privileges()

    # Create log directory if needed
    log_dir = Path(os.path.expanduser("~/.risk_manager/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    install_service()

    # Ask if user wants to start now
    response = input("Start service now? [y/n]: ")
    if response.lower() == 'y':
        start_service()
    else:
        print(f"Service installed but not started.")
        print(f"Start with: sc start {SERVICE_NAME}")

    print("\nInstallation complete!")
    print(f"View service status: sc query {SERVICE_NAME}")
    print(f"View service config: nssm edit {SERVICE_NAME}")

if __name__ == "__main__":
    main()
```

---

## Service Uninstallation Script

**File**: `scripts/uninstall_service.py`

```python
#!/usr/bin/env python3
"""
Uninstall Risk Manager Daemon Windows service.

Usage:
    python uninstall_service.py
"""

import subprocess
import sys

SERVICE_NAME = "RiskManagerDaemon"

def check_admin_privileges():
    """Verify script is run with administrator privileges."""
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        is_admin = False

    if not is_admin:
        print("ERROR: This script must be run as Administrator")
        sys.exit(1)

def stop_service():
    """Stop service if running."""
    print(f"Stopping {SERVICE_NAME}...")

    result = subprocess.run(["sc", "stop", SERVICE_NAME], capture_output=True, text=True)

    if "STOP_PENDING" in result.stdout or "STOPPED" in result.stdout:
        print("Service stopped")
    elif "service has not been started" in result.stderr:
        print("Service was not running")
    else:
        print(f"WARNING: {result.stdout}")

def uninstall_service():
    """Remove service using NSSM."""
    nssm = shutil.which("nssm")
    if not nssm:
        print("NSSM not found, trying sc delete...")
        result = subprocess.run(["sc", "delete", SERVICE_NAME], capture_output=True, text=True)
    else:
        result = subprocess.run([nssm, "remove", SERVICE_NAME, "confirm"], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Service {SERVICE_NAME} uninstalled successfully")
    else:
        print(f"ERROR: Failed to uninstall service: {result.stderr}")
        sys.exit(1)

def cleanup_files():
    """Ask if user wants to delete config/state files."""
    print("\nService uninstalled.")
    response = input("Delete configuration and state files? [y/n]: ")

    if response.lower() == 'y':
        import shutil
        from pathlib import Path

        config_dir = Path.home() / ".risk_manager"
        if config_dir.exists():
            shutil.rmtree(config_dir)
            print(f"Deleted {config_dir}")
    else:
        print("Configuration and state files preserved")

def main():
    print("=" * 60)
    print("Risk Manager Daemon - Service Uninstallation")
    print("=" * 60)

    check_admin_privileges()

    stop_service()
    uninstall_service()
    cleanup_files()

    print("\nUninstallation complete!")

if __name__ == "__main__":
    main()
```

---

## Service Management Scripts

### Start Service

```powershell
# start_daemon.ps1
$SERVICE_NAME = "RiskManagerDaemon"

$status = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue

if ($null -eq $status) {
    Write-Host "ERROR: Service not installed"
    exit 1
}

if ($status.Status -eq "Running") {
    Write-Host "Service is already running"
} else {
    Start-Service -Name $SERVICE_NAME
    Write-Host "Service started successfully"
}
```

### Stop Service

```powershell
# stop_daemon.ps1
$SERVICE_NAME = "RiskManagerDaemon"

$status = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue

if ($null -eq $status) {
    Write-Host "ERROR: Service not installed"
    exit 1
}

if ($status.Status -eq "Stopped") {
    Write-Host "Service is already stopped"
} else {
    Stop-Service -Name $SERVICE_NAME
    Write-Host "Service stopped successfully"
}
```

### Restart Service

```powershell
# restart_daemon.ps1
$SERVICE_NAME = "RiskManagerDaemon"

Restart-Service -Name $SERVICE_NAME
Write-Host "Service restarted successfully"
```

---

## Daemon Entry Point (main.py)

The daemon must be modified to handle Windows service lifecycle signals:

```python
# src/main.py
"""
Risk Manager Daemon entry point.

Can run as:
1. Foreground process (for testing)
2. Windows service (via NSSM wrapper)
"""

import asyncio
import signal
import sys
import logging

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True

async def main_loop():
    """Main daemon event loop."""
    from config_manager import ConfigManager
    from daemon.event_bus import EventBus
    from core.risk_engine import RiskEngine
    # ... (import other components)

    # Initialize components
    config = ConfigManager()
    config.load_all()

    event_bus = EventBus()
    risk_engine = RiskEngine(config, event_bus)
    # ... (initialize other components)

    # Start daemon
    await risk_engine.start()

    logging.info("Risk Manager Daemon started successfully")

    # Main loop
    while not shutdown_requested:
        await asyncio.sleep(1)
        # Periodic health checks, state saves, etc.

    # Graceful shutdown
    logging.info("Shutting down gracefully...")
    await risk_engine.stop()
    # ... (stop other components)

    logging.info("Daemon stopped")

def main():
    """Entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run async main loop
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## Testing the Service

### Manual Test Sequence

```powershell
# 1. Install service (as Administrator)
python scripts/install_service.py

# 2. Verify service registered
sc query RiskManagerDaemon

# 3. Start service
sc start RiskManagerDaemon

# 4. Check service status
sc query RiskManagerDaemon
# Should show: STATE: RUNNING

# 5. View logs
Get-Content ~\.risk_manager\logs\service_stdout.log -Tail 50

# 6. Test graceful stop
sc stop RiskManagerDaemon

# 7. Verify stopped cleanly
# Check logs for "Daemon stopped" message

# 8. Test auto-restart on crash
# Kill daemon process manually
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq Risk*"

# Wait 10 seconds, verify service restarts
sc query RiskManagerDaemon

# 9. Test unkillable by regular user
# Log in as regular user (not admin)
# Try to stop service
sc stop RiskManagerDaemon
# Should get: Access is denied.

# 10. Uninstall service
python scripts/uninstall_service.py
```

---

## Service Recovery Configuration

NSSM provides built-in recovery settings. Configure via:

```powershell
# Edit service recovery settings
nssm set RiskManagerDaemon AppExit Default Restart

# First failure: Restart after 10 seconds
nssm set RiskManagerDaemon AppRestartDelay 10000

# Throttle restarts: No more than 3 in 5 minutes
nssm set RiskManagerDaemon AppThrottle 300000

# Reset failure count after 1 hour of successful operation
# (Done automatically by Windows Service Manager)
```

---

## Unkillable Implementation Verification

### Test as Regular User

```powershell
# As regular user (not administrator)

# Try Task Manager
# 1. Open Task Manager
# 2. Look for python.exe process running daemon
# 3. Try to end process
# Expected: Access Denied or process not visible

# Try command line
taskkill /PID <daemon_pid>
# Expected: ERROR: Access is denied.

# Try service control
sc stop RiskManagerDaemon
# Expected: Access is denied.

net stop RiskManagerDaemon
# Expected: System error 5 has occurred. Access is denied.
```

### Test as Administrator

```powershell
# As administrator

# Should be able to stop
sc stop RiskManagerDaemon
# Expected: Success

# Should be able to kill process
taskkill /F /PID <daemon_pid>
# Expected: Success (but service will restart it)
```

---

## Logging and Monitoring

### Service Logs

NSSM automatically captures:
- **Stdout**: `~/.risk_manager/logs/service_stdout.log`
- **Stderr**: `~/.risk_manager/logs/service_stderr.log`

These are separate from daemon's own structured logs.

### Windows Event Log

Critical service events are logged to Windows Event Log:

```powershell
# View service events
Get-EventLog -LogName Application -Source RiskManagerDaemon -Newest 50
```

To enable Event Log integration, configure NSSM:

```powershell
nssm set RiskManagerDaemon AppEvents 1
```

---

## Troubleshooting

### Service Won't Start

```powershell
# Check service status
sc query RiskManagerDaemon

# View detailed error
sc qc RiskManagerDaemon

# Check logs
Get-Content ~\.risk_manager\logs\service_stderr.log

# Common issues:
# 1. Python not in PATH
# 2. Config files missing
# 3. Permissions issue on log directory
```

### Service Restarts Too Frequently

```powershell
# Check restart count
nssm dump RiskManagerDaemon

# Increase throttle window
nssm set RiskManagerDaemon AppThrottle 600000  # 10 minutes

# View crash logs
Get-Content ~\.risk_manager\logs\service_stderr.log -Tail 100
```

---

## Summary for Implementation Agent

**To implement Windows Service Wrapper, you must:**

1. **Download NSSM 2.24+** and add to system PATH

2. **Create installation scripts**:
   - `scripts/install_service.py` (Administrator required)
   - `scripts/uninstall_service.py` (Administrator required)

3. **Modify daemon entry point** (`src/main.py`):
   - Handle SIGTERM for graceful shutdown
   - Implement async main loop
   - Add proper logging to stdout/stderr

4. **Configure service recovery**:
   - Auto-restart on failure (10s delay)
   - Throttle restarts (max 3 per 5 min)
   - Graceful shutdown timeout (30s)

5. **Test unkillable behavior**:
   - Verify regular user cannot stop service
   - Verify administrator can stop service
   - Verify auto-restart after crash

6. **Document installation procedure** for users

**Critical Notes:**
- Service MUST run as Administrator or SYSTEM account
- Graceful shutdown MUST persist state before exit
- Log directory MUST exist before service starts
- Configuration MUST be validated before daemon starts

**Dependencies**: Configuration System (16)
**Blocks**: Admin CLI (18), IPC API (23)
**Priority**: P0 (required for production deployment)
