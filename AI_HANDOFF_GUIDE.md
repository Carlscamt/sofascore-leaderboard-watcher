# AI Developer Handoff Guide: Sofascore Monitor

## 1. Project Overview
**Goal**: Monitor specific "tipsters" (users) on Sofascore for new betting predictions and send real-time alerts to Discord.
**Stack**: Python 3.10+, SQLite (Async/WAL), Discord Webhooks.
**Structure**: `src`-layout package (`src/sofascore_monitor/`).
**Key Libraries**: `aiohttp`, `sqlite3`, `discord-webhook`.

## 2. Architecture & Data Flow
1.  **Monitor Loop (`src/sofascore_monitor/monitor.py`)**: 
    - Runs indefinitely with a configurable scan interval (default 5 mins).
    - `check_all_users()` -> `check_user(user)` concurrently.
2.  **Client (`src/sofascore_monitor/client.py`)**: 
    - Handles HTTP requests to Sofascore API.
    - Uses `tls_client` (if available) to bypass fingerprinting, falls back to `requests`.
    - Proxies support via `PROXY_URL`.
3.  **Storage (`src/sofascore_monitor/storage.py`)**: 
    - Async wrapper around synchronous `sqlite3`.
    - Tables: `seen_bets` (deduplication), `user_status` (rate limiting/pausing).
4.  **Notifications (`src/sofascore_monitor/notifications.py`)**:
    - Formats Discord embeds with rich stats (Current ROI/Profit).
    - Rate limit handling (429 retries).

## 3. Key Components & APIs

### A. Monitor (`monitor.py`)
- **`Monitor(use_auto_discovery=True)`**: Entry point.
- **`discover_users()`**: Fetches top predictors from leaderboard and adds them to monitoring list if `TOP_PREDICTORS_LIMIT` allows.
- **`check_user(user)`**: Core logic. Checks DB for pause status -> Fetches Bets -> Parses -> Filters Seen -> Saves -> Alerts.

### B. Client (`client.py`)
- **`SofascoreClient`**:
    - `fetch(endpoint)`: Generic async fetch.
    - `get_user_predictions(user_id, page)`: Main data source.
    - `get_top_predictors()`: For auto-discovery.
- **Error Handling**: Raises `UserNotFoundError` (404), returns `None` on 429/500 to invoke backoff.

### C. Storage (`storage.py`)
- **`is_seen(bet_id)`** -> `bool`: Check if bet already processed.
- **`add_seen(bet_id, user_id)`**: Mark bet as processed.
- **`get_user_status(user_id)`** -> `(failures, paused_until)`: For individual circuit breaking.
- **`increment_failure(...)`**: Triggers pause if `MAX_RETRIES` exceeded.

### D. Data Models (`src/sofascore_monitor/models.py`)
- **`User`**: `id`, `name`, `roi`, `slug`, `current_roi`, `current_profit`.
- **`Bet`**: `id` (unique key), `market_name`, `choice_name`, `odds`, `start_time` (for filtering).

## 4. Configuration (`src/sofascore_monitor/config.py`) & Environment
- **Private Keys**: `DISCORD_WEBHOOK_URL`, `PROXY_URL` (in `.env`).
- **Tunables**: 
    - `SCAN_INTERVAL_MINUTES` (Default: 5).
    - `TOP_PREDICTORS_LIMIT` (Default: 10).
- **Filters**:
    - `MIN_ROI`, `MIN_AVG_ODDS`, `MIN_TOTAL_BETS` (User filters).
    - `TIME_LOOKAHEAD_HOURS` (24), `MATCH_GRACE_PERIOD_MINUTES` (5).

## 5. Instructions for AI Agents
**Context**: You are an autonomous developer agent.
**Objective**: Maintain, debug, or extend this service.

### Common Tasks & Patterns
1.  **Adding a New Feature**:
    - **Step 1**: Check `models.py` if new data fields are needed.
    - **Step 2**: Update `Storage._init_db` in `storage.py` (add columns safely or new table).
    - **Step 3**: Update `Monitor` logic.
2.  **Debugging "No Alerts"**:
    - Check `monitor.log` for "429 Rate limited" (IP ban) or "User Not Found" (ID changed).
    - Check `sofascore_monitor.db` `user_status` table for `paused_until` timestamps.
3.  **Refactoring**:
    - `monitor.py` is the orchestrator. Keep it clean. Move complex parsing to a helper if it grows.
    - `client.py` is critical for evasion. *Do not remove* `tls_client` fallback logic without confirming the environment supports it.

### "Least Context" Quick Start
- **Run**: `python main.py`
- **Tests**: `pytest tests/`
- **Logs**: `tail -f monitor.log`

## 6. Known Issues / Gotchas
- **Rate Limits**: Sofascore is aggressive. Do not lower `POLL_INTERVAL_SECONDS` below 30s without rotating proxies.
- **Bet IDs**: Parsing logic in `monitor.py` (lines 165-167) attempts to create a unique key. It's fragile. If duplicates appear, check this logic first.
- **Discord**: Webhook limits are 5 requests/2s. `notifications.py` handles this naively with sleeps.

## 7. Recommended Next Actions
- **Integrate Proxy Rotation**: Current implementation uses a single static `PROXY_URL`.
- **Better ID Generation**: Use a hash of `(eventId, marketId, choiceId)` instead of fragile string concatenation.
- **Dashboard**: Expose `sofascore_monitor.db` via a simple Streamlit app for easier status checking.
