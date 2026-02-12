# Sofascore Leaderboard Monitor

> **Status:** Production Ready (Hardened)

A robust, standalone tool to monitor Top Predictors on Sofascore and send real-time alerts to Discord when they place new bets. Designed for reliability, scalability, and ease of deployment.

## Key Features

-   **Auto-Discovery**: Automatically finds and monitors top predictors from the leaderboard.
-   **Async Architecture**: Efficiently polls hundreds of users concurrently using `asyncio`.
-   **Resilience & Anti-Bot**:
    -   Intelligent backoff strategies (pauses users after repeated failures).
    -   Uses `tls_client` to mimic legitimate browser traffic.
    -   Support for HTTP/HTTPS proxies.
    -   Randomized jitter to avoid detection.
-   **Persistence**: Uses `sqlite3` (WAL mode) to track seen bets and prevent duplicate alerts across restarts.
-   **Dockerized**: Ready for deployment with `docker-compose`.

## Project Structure

This project follows a modern `src`-layout:

```
sofascore_monitor/
├── src/
│   └── sofascore_monitor/  # Core application package
│       ├── monitor.py      # Main monitoring logic
│       ├── client.py       # API client (tls_client wrapper)
│       ├── storage.py      # Database layer
│       └── ...
├── scripts/                # Utility scripts (e.g., check_stats.py)
├── data/                   # Persistent data (SQLite DB)
├── tests/                  # Unit tests
├── main.py                 # Application entry point
├── Dockerfile              # Docker build configuration
└── docker-compose.yml      # Service orchestration
```

## Setup & Installation

### Prerequisites

-   Python 3.10+
-   (Optional) Docker & cli-compose

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone <repository_url>
cd sofascore_monitor
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory (copy from `.env.example`):

```ini
# .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
PROXY_URL=http://user:pass@host:port  # Optional
TOP_PREDICTORS_LIMIT=10               # Number of top users to track
POLL_INTERVAL_SECONDS=60              # Seconds between checks
```

## Usage

### Option A: Local Python

Run the monitor directly from the project root:

```bash
python main.py
```

### Option B: Docker (Recommended)

Build and run the container in the background:

```bash
docker-compose up -d --build
```

View logs:
```bash
docker-compose logs -f
```

## Utility Scripts

The `scripts/` directory contains tools for debugging and manual checks. You can run them directly from the root:

-   **Check Leaderboard Stats**: Verification of API connectivity and data parsing.
    ```bash
    python scripts/check_stats.py
    ```
-   **Debug Database**: Inspect the SQLite database state.
    ```bash
    python scripts/debug_db.py
    ```

## Development

### Running Tests

The project uses `pytest` for testing.

1.  Install test dependencies:
    ```bash
    pip install pytest pytest-asyncio
    ```

2.  Run the test suite:
    ```bash
    python -m pytest
    ```

## Hardening Details

-   **User Pausing**: If a monitored user fails to return data 3 times consecutively (e.g., 404 or persistent API errors), they are paused for 30 minutes to reduce API load.
-   **Data Retention**: To keep the database lean, bets older than 30 days are automatically pruned on startup.
-   **WAL Mode**: The SQLite database uses Write-Ahead Logging for better concurrency.
