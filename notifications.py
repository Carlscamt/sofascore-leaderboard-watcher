import logging
import requests
import json
from models import Bet, User
from config import DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)

def send_discord_alert(user: User, bet: Bet):
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        embed = {
            "title": "🚨 New Bet Alert!",
            "color": 5814783, # Greenish
            "fields": [
                {"name": "Predictor", "value": f"[{user.name}](https://www.sofascore.com/user/{user.slug}/{user.id})", "inline": True},
                {"name": "Sport", "value": bet.sport, "inline": True},
                {"name": "Match", "value": f"Event ID: {bet.event_id}", "inline": False}, # Enhanced later with match names if available
                {"name": "Bet", "value": f"**{bet.market_name}**: {bet.choice_name}", "inline": True},
                {"name": "Odds", "value": str(bet.odds), "inline": True},
            ],
            "footer": {"text": "Sofascore Monitor • Antigravity"}
        }

        payload = {
            "embeds": [embed]
        }

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 204:
            logger.error(f"Failed to send Discord alert: {response.text}")

    except Exception as e:
        logger.error(f"Error sending Discord webhook: {e}")
