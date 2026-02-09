# Sofascore Leaderboard Monitor

A hardened, standalone tool to monitor Top Predictors on Sofascore and alert when they place new bets.

**Status**: Production Ready (Hardened)

**Features**:
-   **Auto-Discovery**: Automatically finds top predictors from the leaderboard.
-   **Async Polling**: Efficiently monitors hundreds of users concurrently.
-   **Resilience**: Intelligent backoff (pause users after 3 failures) and SQLite WAL mode.
-   **Persistence**: Uses `sqlite3` to remember bets across restarts.
-   **Alerts**: detailed Discord Webhooks.
-   **Anti-Bot**: Uses `tls_client`, randomized jitter, and Proxy support.
-   **Docker Ready**: Multi-stage build for minimal footprint.

## Setup

1.  **Dependencies**:
    ```bash
    pip install -r sofascore_monitor/requirements.txt
    ```

2.  **Configuration**:
    Create a `.env` file in `sofascore_monitor/` (copy from `.env.example`):
    ```ini
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    PROXY_URL=http://user:pass@host:port (Optional)
    ```

## Running

### Option 1: Local Python
```bash
python sofascore_monitor/main.py
```

### Option 2: Docker (Recommended)
```bash
cd sofascore_monitor
docker-compose up -d
```
View logs with `docker-compose logs -f`.

## Hardening Details
-   **User Pausing**: If a user fails to load 3 times in a row, they are paused for 30 minutes.
-   **Data Retention**: Bets older than 30 days are auto-deleted on startup.
-   **WAL Mode**: Database is optimized for concurrent writes.
