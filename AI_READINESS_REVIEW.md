# AI Readiness Review - Sofascore Monitor

## 1. Project Overview
- **Name**: `sofascore_monitor` (Sofascore Leaderboard Monitor)
- **Purpose**: A Python-based automation tool to discover and track "Top Predictors" on Sofascore and alert the user (via CLI) when new bets are placed.
- **Key Feature**: Uses reverse-engineered API endpoints to find users and fetch their real-time predictions, bypassing standard bot protection.

## 2. Technology Stack & Dependencies
- **Language**: Python 3.10+
- **Networking**: 
  - `tls_client`: Used to mimic a real browser (Firefox/Chrome) and manage TLS fingerprints to bypass 403 Forbidden errors (Cloudflare/Akamai).
  - `requests`: Fallback HTTP client (rarely used due to blocks).
- **Data Models**: Python `dataclasses` (`User`, `Bet`).
- **Storage**: In-memory `set` logic for bet deduplication (volatile).
- **Architecture Pattern**: Sync Polling Loop (Infinite `while True`).
- **Configuration**: Static Python file (`config.py`).

## 3. Core Processes

### A. Auto-Discovery
1. **Trigger**: On startup (and potentially periodic).
2. **Endpoint**: `GET /api/v1/user-account/vote-ranking`
3. **Process**: Fetches the top users, parses their string IDs (MongoDB style) or legacy integer IDs, and adds them to the monitoring list if not already present.

### B. Monitoring Loop
1. **Trigger**: Every 60 seconds (Configurable).
2. **Process**: Iterates through each `User` object.
3. **Action**: Calls `GET /api/v1/user-account/{id}/predictions`.
4. **Deduplication**: Checks if `customId` or `eventId` is in `self.seen_bets`.
5. **Alert**: If new, prints to console.

## 4. Known Constraints & Areas for Improvement
- **Validation**: Current dedup is in-memory; restarting the app loses history and may re-alert on existing active bets.
- **Concurrency**: The loop is blocking/synchronous. Monitoring hundreds of users might drift the 60s window significantly.
- **Notifications**: Console-only. No push/webhook integration yet.
- **Evasion**: Relies on `tls_client`, but aggressive polling could still trigger IP bans.
- **Deployment**: Local script execution (`run.bat`). No Docker/containerization.

---

## 5. Prompt for AI Recommendations

**Copy and paste the prompt below to an AI assistant:**

```text
Act as a Senior Python Architect and Site Reliability Engineer. 
Review the following project details for a "Sofascore Leaderboard Monitor" application and provide a prioritized list of recommendations to improve its robustness, scalability, and maintainability.

**Current Stack**: Python, tls_client, In-Memory Storage, Synchronous Loop.

**Specific Areas to Analyze**:
1.  **Persistence**: How can we persist "seen bets" to avoid re-alerting after a restart without using a heavy database like PostgreSQL? (Consider SQLite/JSON/LevelDB).
2.  **Concurrency**: The current synchronous loop will lag if we monitor 500+ users. Recommend a concurrency model (AsyncIO vs Threading) compatible with `tls_client`.
3.  **Notifications**: Suggest a lightweight way to push alerts to a phone or Discord/Telegram.
4.  **Anti-Detection**: Are there better strategies for the polling interval (jitter, rotation) to avoid IP bans?
5.  **Deployment**: How can this run 24/7 on a cheap VPS or Raspberry Pi? Usage of Docker?

**Constraint**: Keep the solution lightweight and easy to deploy for a single user.
```
