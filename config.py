import os
from dotenv import load_dotenv

load_dotenv()

# Output Configuration
ENABLE_CONSOLE_LOGS = os.getenv("ENABLE_CONSOLE_LOGS", "True").lower() == "true"
ENABLE_DESKTOP_NOTIFICATIONS = os.getenv("ENABLE_DESKTOP_NOTIFICATIONS", "True").lower() == "true"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
PROXY_URL = os.getenv("PROXY_URL", "") # Format: http://user:pass@host:port

# Persistence
DB_PATH = os.getenv("DB_PATH", "sofascore_monitor.db")

# API Configuration
SOFASCORE_BASE_URL = "https://www.sofascore.com/api/v1"

# Hardening
MAX_RETRIES = 3
PAUSE_DURATION_MINUTES = 30
RETENTION_DAYS = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Legacy / Manual Monitoring
POLL_INTERVAL_SECONDS = 60
TOP_PREDICTORS_LIMIT = 10 # Only monitor the top N predictors
TARGET_USERS = [
    # Example User (Replace with real Top Predictor IDs)
    # Using 'Sofascore' (Team ID: 857093) as a placeholder - COMMENTED OUT to prevent 404s
    # {"id": 857093, "name": "Sofascore", "slug": "sofascore"}, 
]
