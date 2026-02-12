# 🚀 Deploy Sofascore Monitor - Native Systemd Migration

## Mission Context

You are deploying a **refactored Python monitoring application** that tracks sports betting predictions from Sofascore's leaderboard and sends alerts to Discord. The application previously ran in Docker but has been **migrated to native systemd** for better performance on old laptop hardware.

## System Environment

- **Host**: Linux Mint (Ubuntu-based)
- **IP**: 192.168.123.2
- **User**: carlscamt / Password: 7373
- **Project Path**: `~/antigravity/sofascore-leaderboard-watcher`
- **Python Version Required**: 3.11+

## Application Architecture

### Core Functionality
1. **Auto-Discovery**: Fetches top predictors from Sofascore global leaderboard
2. **Filtering**: Monitors only users meeting criteria (MIN_ROI, MIN_AVG_ODDS, MIN_TOTAL_BETS)
3. **Adaptive Polling**: Time-based intervals (fast during peak betting hours 18-23h, slow at night 0-6h)
4. **Deduplication**: SQLite database (WAL mode) tracks seen bets
5. **Alerts**: Sends Discord webhook notifications for new predictions
6. **Line Movement**: Tracks odds changes >15% and alerts on significant moves

### Project Structure (Post-Refactor)
```
~/antigravity/sofascore-leaderboard-watcher/
├── src/
│   └── sofascore_monitor/
│       ├── __init__.py
│       ├── monitor.py        # Main polling loop with adaptive intervals
│       ├── models.py          # Data models (User, Bet, OddsSnapshot)
│       ├── client.py          # HTTP client (tls-client wrapped in asyncio)
│       ├── storage.py         # SQLite storage layer (async wrappers)
│       ├── notifications.py   # Discord webhook sender
│       └── config.py          # Configuration from .env
├── main.py                    # Entry point
├── requirements.txt
├── .env                       # Configuration (not in git)
├── data/
│   └── sofascore_monitor.db  # SQLite database (auto-created)
├── logs/                      # Optional log directory
└── tests/
```

### Key Technologies
- **Concurrency**: asyncio event loop
- **HTTP**: tls-client (mimics Chrome, wrapped in asyncio.to_thread)
- **Database**: SQLite with WAL mode, async operations via to_thread
- **Resource Limits**: BoundedSemaphore (max 5 concurrent HTTP requests)

## Recent Optimizations (Laptop Hardware)

These features are **already implemented in code**:

1. **Behavioral Polling**: `calculate_adaptive_interval()` adjusts scan frequency based on London timezone:
   - Peak (18-23h): 3.5-5 min intervals
   - Night (0-6h): 10-15 min intervals  
   - Weekend: 15% faster polling

2. **Resource Bounding**: HTTP semaphore limits concurrent requests to 5 (prevents memory spikes)

3. **Line Movement Tracking**: Single-row schema in `latest_odds` table alerts on >15% odds changes

4. **WAL Mode**: Database runs in Write-Ahead Logging mode for concurrency

## Deployment Tasks

### Task 1: Environment Setup

```bash
# 1. Verify Python Version (Must be 3.11+)
python3 --version

# 2. Navigate to project
cd ~/antigravity/sofascore-leaderboard-watcher

# 3. Create Python virtual environment
python3.11 -m venv venv

# 4. Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verify dependencies (including tls-client and pytz)
pip list | grep -E "tls-client|pytz"

# 6. Verify imports work with new src-layout structure
PYTHONPATH=./src python3 -c "from sofascore_monitor.monitor import MonitorService; print('✅ Imports OK')"
```

### Task 2: Configuration

Create/verify `.env` file with absolute paths:

```bash
nano .env
```

**Required contents**:
```ini
# Discord Webhook
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID

# Monitoring Settings
SCAN_INTERVAL_MINUTES=5
MIN_ROI=5.0
MIN_AVG_ODDS=1.5
MIN_TOTAL_BETS=10

# Database (use absolute path)
DB_PATH=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/data/sofascore_monitor.db

# Logging
LOG_LEVEL=INFO
```

### Task 3: Database Initialization

```bash
# Optional: Backup existing data if migrating
if [ -f data/sofascore_monitor.db ]; then
    cp data/sofascore_monitor.db data/sofascore_monitor.db.backup
    echo "✅ Existing database backed up"
fi

# Ensure data directory exists
mkdir -p data

# Initialize database with WAL mode and create tables
python3 << 'EOF'
import sys
sys.path.insert(0, './src')
from sofascore_monitor.storage import StorageLayer

storage = StorageLayer()
storage.initialize()  # Creates tables: seen_bets, user_status, latest_odds
print('✅ Database initialized')
EOF
```

### Task 4: Create Systemd Service

```bash
sudo nano /etc/systemd/system/sofascore-monitor.service
```

**Service file contents** (copy exactly):

```ini
[Unit]
Description=Sofascore Leaderboard Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=carlscamt
Group=carlscamt
WorkingDirectory=/home/carlscamt/antigravity/sofascore-leaderboard-watcher

# Environment variables
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/src"
Environment="TZ=Europe/London"
EnvironmentFile=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/.env

# Execution
ExecStart=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/venv/bin/python main.py

# Restart policy (60s delay to prevent rapid restart loops on old hardware)
Restart=on-failure
RestartSec=60
StartLimitBurst=5
StartLimitIntervalSec=600

# Resource limits (CRITICAL for old laptop - prevents thermal throttling)
MemoryMax=400M
MemoryHigh=350M
CPUQuota=40%
TasksMax=50

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/data
ReadWritePaths=/home/carlscamt/antigravity/sofascore-leaderboard-watcher/logs
CapabilityBoundingSet=

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sofascore-monitor

[Install]
WantedBy=multi-user.target
```

### Task 5: Start and Enable Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable sofascore-monitor.service

# Start the service
sudo systemctl start sofascore-monitor.service

# Verify it's running
sudo systemctl status sofascore-monitor.service
```

**Expected status output**:
```
● sofascore-monitor.service - Sofascore Leaderboard Monitor
     Loaded: loaded (/etc/systemd/system/sofascore-monitor.service; enabled)
     Active: active (running) since Wed 2026-02-11 20:10:00 CST
   Main PID: 12345 (python)
      Tasks: 6 (limit: 50)
     Memory: 82.5M (high: 350.0M max: 400.0M)
        CPU: 1.234s
```

### Task 6: Laptop Power Management

**Prevent suspend when lid is closed** (critical for 24/7 operation):

```bash
# Edit logind configuration
sudo nano /etc/systemd/logind.conf
```

**Add these lines** (uncomment if present):
```ini
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
```

```bash
# Apply changes
sudo systemctl restart systemd-logind.service

# Verify (no need to log out)
echo "✅ Lid close will no longer suspend system"
```

## Verification Steps

### 1. Service Health Check
```bash
# Wait 30 seconds for first poll cycle
sleep 30

# Check status
sudo systemctl status sofascore-monitor.service
# Expected: active (running)

# Check logs for discovery
sudo journalctl -u sofascore-monitor.service --since "1 minute ago" | grep -E "Discovered|Next poll"
```

### 2. Memory Compliance Check
```bash
MEMORY_MB=$(echo "scale=0; $(systemctl show sofascore-monitor.service --property=MemoryCurrent --value) / 1024 / 1024" | bc)
echo "Memory usage: ${MEMORY_MB}MB (limit: 350MB soft, 400MB hard)"
# Expected: < 350MB
```

### 3. Database Integrity Check
```bash
sqlite3 ~/antigravity/sofascore-leaderboard-watcher/data/sofascore_monitor.db "PRAGMA integrity_check;"
# Expected: ok
```

### 4. Check Logs (Real-time)
```bash
sudo journalctl -u sofascore-monitor.service -f
```

**Expected log patterns**:
```
INFO - Starting Async Monitor...
INFO - Discovered 8 users meeting criteria (MIN_ROI=5.0)
INFO - [User: example_user] Processing 12 predictions
INFO - [User: example_user] Found 2 new bets (Match: Team A vs Team B)
INFO - Next poll in 283 seconds (adaptive interval)
```

### Check Resource Usage
```bash
# Memory consumption
systemctl show sofascore-monitor.service --property=MemoryCurrent

# Should output ~80-150MB during idle, <350MB during active polling
```

### Verify Adaptive Polling
```bash
# Check last 10 poll intervals
sudo journalctl -u sofascore-monitor.service --since "30 minutes ago" | grep "Next poll"

# Should show variance based on time of day:
# Peak hours (18-23h London time): 210-300 seconds
# Night (0-6h): 600-900 seconds
# Business hours: 270-420 seconds
```

### Check Database
```bash
# Verify tables exist and WAL mode is active
sqlite3 ~/antigravity/sofascore-leaderboard-watcher/data/sofascore_monitor.db << 'EOF'
PRAGMA journal_mode;
.tables
SELECT COUNT(*) FROM seen_bets;
SELECT COUNT(*) FROM latest_odds;
EOF
```

**Expected output**:
```
wal
seen_bets  user_status  latest_odds
<number>
<number>
```

## Standard Operating Procedures

### View Status
```bash
sudo systemctl status sofascore-monitor.service
```

### View Recent Logs
```bash
sudo journalctl -u sofascore-monitor.service -n 100 --no-pager
```

### Restart Service (after code changes)
```bash
cd ~/antigravity/sofascore-leaderboard-watcher
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart sofascore-monitor.service
```

### Stop Service
```bash
sudo systemctl stop sofascore-monitor.service
```

### Check Memory/CPU Usage
```bash
# Memory in MB
echo "scale=2; $(systemctl show sofascore-monitor.service --property=MemoryCurrent --value) / 1024 / 1024" | bc

# Tasks count (should be < 50)
systemctl show sofascore-monitor.service --property=TasksCurrent
```

## Troubleshooting Guide

### Issue: Service Won't Start

**Diagnosis**:
```bash
sudo journalctl -u sofascore-monitor.service -n 50 --no-pager | grep -i error
```

**Common causes**:
1. **Import errors**: Verify `PYTHONPATH` in service file points to `/home/carlscamt/antigravity/sofascore-leaderboard-watcher/src`
2. **Missing dependencies**: Re-run `pip install -r requirements.txt` in venv
3. **Permission denied**: Check ownership with `ls -la data/`

**Fix permissions**:
```bash
sudo chown -R carlscamt:carlscamt ~/antigravity/sofascore-leaderboard-watcher
chmod 755 ~/antigravity/sofascore-leaderboard-watcher/data
```

### Issue: Database Locked Errors

**Diagnosis**:
```bash
sudo journalctl -u sofascore-monitor.service | grep "database is locked"
```

**Fix**:
```bash
# Stop service
sudo systemctl stop sofascore-monitor.service

# Kill any hung processes
pkill -f "sofascore"

# Verify WAL mode (should output: wal)
sqlite3 ~/antigravity/sofascore-leaderboard-watcher/data/sofascore_monitor.db "PRAGMA journal_mode;"

# Restart
sudo systemctl start sofascore-monitor.service
```

### Issue: High Memory Usage (Approaching 400MB)

**Diagnosis**:
```bash
systemctl status sofascore-monitor.service | grep Memory
```

**Possible causes**:
- HTTP semaphore leak (check code has `async with self.http_semaphore:`)
- Too many unclosed connections

**Temporary fix** (restart clears memory):
```bash
sudo systemctl restart sofascore-monitor.service
```

### Issue: Service Crashes Repeatedly

**Diagnosis**:
```bash
# Check restart counter
systemctl show sofascore-monitor.service --property=NRestarts

# View crash logs
sudo journalctl -u sofascore-monitor.service --since "10 minutes ago"
```

**If > 5 crashes in 10 minutes**, service enters failed state:
```bash
# Reset failure counter after fixing underlying issue
sudo systemctl reset-failed sofascore-monitor.service
sudo systemctl start sofascore-monitor.service
```

## Success Criteria

After deployment, verify these conditions:

- [ ] Service shows `Active: active (running)` in status
- [ ] Logs show "Starting Async Monitor" message
- [ ] Memory usage stays below 350MB (soft limit)
- [ ] CPU quota enforced at 40% (check with `systemctl show`)
- [ ] Database exists in `data/` directory with WAL mode enabled
- [ ] Adaptive polling shows different intervals based on time of day
- [ ] No "database is locked" errors in logs
- [ ] Lid close does not suspend the laptop
- [ ] Service survives reboot (auto-starts)

## Additional Context

**Why Native Systemd (No Docker)**:
- Old laptop hardware (4GB RAM) needs minimal overhead
- Docker daemon alone consumes 50-100MB RAM
- Direct systemd provides better resource control (MemoryHigh triggers GC before OOM)
- CPUQuota prevents thermal throttling on aging hardware

**Why These Resource Limits**:
- `MemoryMax=400M`: Hard cap prevents OOM killer
- `MemoryHigh=350M`: Soft limit triggers early garbage collection
- `CPUQuota=40%`: Leaves 60% for OS and thermal headroom
- `TasksMax=50`: Prevents thread exhaustion if HTTP client fails

**Import System**:
- Package uses **relative imports** internally (`from .models import User`)
- Entry point (`main.py`) uses **absolute imports** (`from sofascore_monitor.monitor import ...`)
- Scripts in `scripts/` add `src/` to `sys.path` dynamically
- Systemd sets `PYTHONPATH` environment variable for proper resolution

***

## Execute Deployment

Run through Tasks 1-6 in sequence. Report any errors with the exact error message and context. After successful deployment, monitor logs for 10 minutes to verify stable operation.
