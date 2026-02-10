import logging
import requests
import json
from typing import List
from models import Bet, User
from config import DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)

def send_discord_alert(user: User, bets: List[Bet]):
    if not DISCORD_WEBHOOK_URL or not bets:
        return

    try:
        # Use first bet for Match/Sport details (assuming grouped by match)
        first_bet = bets[0]
        
        # Build Bet Strings
        bet_lines = []
        for bet in bets:
            bet_lines.append(f"• **{bet.market_name}**: {bet.choice_name} @ {bet.odds}")
            
        bet_content = "\n".join(bet_lines)

        embed = {
            "title": "🚨 New Bet Alert!",
            "color": 5814783, # Greenish
            "fields": [
                {"name": "Predictor", "value": f"[{user.name}](https://www.sofascore.com/user/{user.slug}/{user.id})", "inline": True},
                {"name": "Stats (All Time)", "value": f"ROI: {user.roi or 0:.1f}% | Profit: {user.profit or 0:.0f} | Win: {user.win_rate or 0:.1f}%", "inline": True},
                {"name": "Sport", "value": first_bet.sport, "inline": False},
                {"name": "Match", "value": f"**{first_bet.match_name}**", "inline": False},
                {"name": "Bets", "value": bet_content, "inline": False},
            ],
            "footer": {"text": f"Sofascore Monitor • Antigravity • {len(bets)} new bet(s)"}
        }

        payload = {
            "embeds": [embed]
        }
        
        # Retry loop for rate limits
        import time
        max_retries = 3
        for attempt in range(max_retries):
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:
                return # Success
                
            if response.status_code == 429:
                try:
                    data = response.json()
                    retry_after = data.get('retry_after', 1.0)
                    logger.warning(f"Discord Rate Limited. Sleeping for {retry_after}s...")
                    time.sleep(float(retry_after) + 0.1) # Add buffer
                    continue
                except:
                    time.sleep(1)
                    continue

            # Other error
            logger.error(f"Failed to send Discord alert: {response.text}")
            break

    except Exception as e:
        logger.error(f"Error sending Discord webhook: {e}")
