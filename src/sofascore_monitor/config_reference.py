"""
Configuration Reference for Sofascore Monitor

You can set these variables in your .env file or as environment variables.

# --- Core ---
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
PROXY_URL=http://user:pass@host:port (Optional)
DB_PATH=sofascore_monitor.db (Default: sofascore_monitor.db in /data)

# --- Monitoring Scope ---
TOP_PREDICTORS_LIMIT=10 (Default: 10)
SCAN_INTERVAL_MINUTES=5 (Default: 5 minutes)

# --- User Filters (Applied during Discovery) ---
# Users must meet ALL criteria to be monitored.
MIN_ROI=5.0             # Minimum ROI % (e.g., 5.0)
MIN_AVG_ODDS=1.60       # Minimum Average Odds (Decimal)
MIN_TOTAL_BETS=50       # Minimum Total Bets (All Time)
MIN_WIN_RATE=45.0       # Minimum Win Rate %

# --- Time Filters (Applied per Bet) ---
TIME_LOOKAHEAD_HOURS=24       # Only alert on matches starting within X hours
MATCH_GRACE_PERIOD_MINUTES=5  # Alert on started matches only if < X minutes in
"""
