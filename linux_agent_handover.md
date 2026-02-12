# 🤖 SYSTEM CONTEXT: Linux Monitoring Node

> **ATTENTION AI AGENT:** This document defines your operational environment and administrative access to the dedicated Linux Monitoring Station.

## 1. System Identity & Access

*   **Role**: Dedicated Application Server (Headless)
*   **OS**: Linux Mint (Ubuntu-based)
*   **Hostname**: `192.168.123.2` (Static IP via Direct Ethernet)
*   **User**: `carlscamt`
*   **Password**: `7373`
*   **Root Auth**: `sudo` (uses same password)

### 🔌 Connection Protocol
To manage this node, you must establish an SSH session from the Windows Host:
```powershell
ssh carlscamt@192.168.123.2
# Password: 7373
```

---

## 2. Application Architecture

The node runs a single mission-critical containerized application.

*   **Project Root**: `~/antigravity/sofascore-leaderboard-watcher`
*   **Deployment Method**: Docker Compose
*   **Container Name**: `monitor`
*   **Data Persistence**: SQLite DB mounted at `./data/sofascore.db`

### Docker Configuration (`docker-compose.production.yml`)
*   **Network**: `network_mode: host` (Direct network access)
*   **Restart Policy**: `unless-stopped` (Auto-recovery)
*   **Volumes**:
    *   `./data`: Database storage
    *   `./logs`: Application logs

---

## 3. Operational Action Space

Refer to these standard operating procedures (SOPs) for state changes.

### 🟡 State: Check Status
*Goal: Verify if the system is running healthy.*
```bash
cd ~/antigravity/sofascore-leaderboard-watcher
docker compose -f docker-compose.production.yml ps
# Expected State: 'monitor' -> 'Up'
```

### 🟢 State: Deploy Update
*Goal: Pull latest code from GitHub and re-deploy.*
```bash
cd ~/antigravity/sofascore-leaderboard-watcher
git pull origin main
docker compose -f docker-compose.production.yml up -d --build
```

### 🔵 State: View Logs
*Goal: Debug errors or verify scanning activity.*
```bash
cd ~/antigravity/sofascore-leaderboard-watcher
docker compose -f docker-compose.production.yml logs -f --tail=100 monitor
```

### 🔴 State: Restart Service
*Goal: Fix a stuck process or apply config changes.*
```bash
docker compose -f docker-compose.production.yml restart monitor
```

### 🟣 Power Management
*Goal: Verify headless power optimizations.*
```bash
# Check if powertop auto-tune is active
systemctl status powertop
# Logs should show: "Active: active (exited)" 
```

---

## 4. Troubleshooting Decision Tree

### 🚨 Issue: "Connection Refused" / "Host Unreachable"
1.  **Check Physical Layer**: Is the Ethernet cable connected to the Windows PC?
2.  **Ping Test**: Run `ping 192.168.123.2` on Windows.
    *   *Success (1ms)*: SSH Service might be down -> Reboot laptop manually.
    *   *Failure*: NIC might be down or IP changed.

### 🚨 Issue: "Database Locked"
1.  **Diagnosis**: Check logs for `sqlite3.OperationalError: database is locked`.
2.  **Resolution**: Restart the container (`docker compose restart monitor`). WAL mode should handle concurrency, but NFS/Volume issues can cause locks.

### 🚨 Issue: High Latency / Missed Scrapes
1.  **Diagnosis**: Check CPU usage. governor should be `powersave` but not throttling critical tasks.
2.  **Check**: `uptime` (load average) and `docker stats monitor`.

---

## 5. Maintenance Schedule

*   **Weekly**: Check disk space (`df -h`). Prune old docker images (`docker image prune -a`).
*   **Monthly**: `git pull` and rebuild to get OS security updates in the base image.
