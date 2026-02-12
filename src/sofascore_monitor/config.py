import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Output Configuration
ENABLE_CONSOLE_LOGS = os.getenv("ENABLE_CONSOLE_LOGS", "True").lower() == "true"
ENABLE_DESKTOP_NOTIFICATIONS = os.getenv("ENABLE_DESKTOP_NOTIFICATIONS", "True").lower() == "true"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
PROXY_URL = os.getenv("PROXY_URL", "") # Format: http://user:pass@host:port

# Persistence
# Use absolute path anchored to this file location
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "sofascore_monitor.db"))

# API Configuration
SOFASCORE_BASE_URL = "https://www.sofascore.com/api/v1"

# Hardening
MAX_RETRIES = 3
PAUSE_DURATION_MINUTES = 30
RETENTION_DAYS = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# User Filters
MIN_ROI = float(os.getenv("MIN_ROI", "0.0"))
MIN_AVG_ODDS = float(os.getenv("MIN_AVG_ODDS", "1.5")) # Minimum Decimal Odds (e.g. 1.50)
MIN_TOTAL_BETS = int(os.getenv("MIN_TOTAL_BETS", "0"))
MIN_WIN_RATE = float(os.getenv("MIN_WIN_RATE", "0.0"))

# Time Filters
TIME_LOOKAHEAD_HOURS = int(os.getenv("TIME_LOOKAHEAD_HOURS", "24"))
MATCH_GRACE_PERIOD_MINUTES = int(os.getenv("MATCH_GRACE_PERIOD_MINUTES", "5"))

# Legacy / Manual Monitoring
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
POLL_INTERVAL_SECONDS = SCAN_INTERVAL_MINUTES * 60
TOP_PREDICTORS_LIMIT = int(os.getenv("TOP_PREDICTORS_LIMIT", "10")) # Only monitor the top N predictors
TARGET_USERS = [
    # Example User (Replace with real Top Predictor IDs)
    # Using 'Sofascore' (Team ID: 857093) as a placeholder - COMMENTED OUT to prevent 404s
    # {"id": 857093, "name": "Sofascore", "slug": "sofascore"}, 
]
