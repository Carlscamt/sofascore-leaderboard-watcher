# Sofascore Leaderboard Monitor - System Context & AI Review Request (V2)

## 1. Project Overview
**Name**: Sofascore Leaderboard Monitor
**Purpose**: A real-time monitoring service that tracks the "Top 10 Predictors" on Sofascore, identifies their new betting tips, and sends consolidated notifications to Discord.
**Current Status**: Production-ready MVP with recent hardening (Async I/O, Rate Limit Handling, Anti-Bot Jitter).

## 2. Technology Stack
-   **Language**: Python 3.x
-   **Concurrency**: `asyncio` (Event Loop)
-   **HTTP Client**: `tls-client` (mimics Chrome/Firefox) wrapped in `asyncio.to_thread` to prevent blocking.
-   **Database**: SQLite (`sofascore_monitor.db`) running in **WAL Mode**.
    -   *Recent Change*: All DB operations are now wrapped in `asyncio.to_thread` to ensure the main event loop is never blocked by file I/O.
-   **Configuration**: `.env` file credentials.
-   **Logging**: Standard `logging` (UTF-8 enforced).

## 3. Core Architecture
### A. Monitor (`monitor.py`)
-   **Discovery**: Fetches global leaderboard.
-   **Polling Strategy**:
    -   *Recent Change*: Implemented **Randomized Jitter**. Instead of a fixed 60s, it sleeps for `POLL_INTERVAL * random.uniform(0.9, 1.25)` (approx 54s - 75s) to evade static analysis bot detection.
-   **Logic**:
    1.  Checks "Strike System" (paused users).
    2.  Fetches predictions.
    3.  Filters: Deduplication (SQLite), Finished Matches.
    4.  **Grouping**: Batches bets by `event_id` to send single, clean alerts per match.

### B. Storage (`storage.py`)
-   **Async Wrapper**: Uses `run_in_executor` pattern (via `to_thread`) for all `sqlite3` calls.
-   **Schema**: `seen_bets` (dedup), `user_status` (rate limit tracking).

### C. Notifications (`notifications.py`)
-   **Reliability**: Smart retry loop for Discord `429` errors (respects `retry_after` header).
-   **Features**: Rich Embeds with ROI/Profit stats and full Match Names.

## 4. Work in Progress / Known Limitations
-   **HTTP Client**: Still using `tls-client` in threads. We are considering switching to `curl_cffi` for native async support but haven't migrated yet.
-   **Scaling**: Currently monitors ~10 users. SQLite is fine now, but we are unsure of the breaking point.

---

## 5. PROMPT FOR AI REVIEW
**Role**: You are a Senior Software Architect and Python Efficiency Expert.

**Task**: Review the **updated** system described above. We have just implemented "Non-blocking SQLite" and "Randomized Polling". Analyze the remaining architecture.

**Please answer the following:**

1.  **Refactoring**: We are currently wrapping `tls-client` and `sqlite3` in threads. Is it worth the effort to refactor to **native async** libraries like `curl_cffi` (for HTTP) and `aiosqlite` (for DB)? Or is the threading overhead negligible for <100 users?
2.  **Next-Level Anti-Bot**: We added jitter. What is the next most impactful change to avoid detection? (e.g. Header rotation, Session persistence, Fingerprint shuffling?)
3.  **Deployment**: If we want to deploy this to a $5 VPS (DigitalOcean/Linode), what process management strategy (Docker vs Systemd) do you recommend for a Python async daemon?
4.  **Feature**: How would you implement "Line Movement Tracking" (detecting when odds drop significantly) on top of this existing polling loop?

**Output Format**: Provide 3 "Next Steps" prioritized by impact.
