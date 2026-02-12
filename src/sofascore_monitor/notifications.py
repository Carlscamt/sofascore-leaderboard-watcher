import logging
import requests
import json
from datetime import datetime
from urllib.parse import quote
from typing import List
from .models import Bet, User
from .config import DISCORD_WEBHOOK_URL, DISCORD_HEALTH_WEBHOOK_URL

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

        # Prepare Links
        # User Link: https://www.sofascore.com/user/profile/{user.id}
        user_link = f"https://www.sofascore.com/user/profile/{user.id}"
        
        # Match Link (use first bet)
        slug = first_bet.event_slug or "match"
        sport = first_bet.sport or "sport"
        custom_id = first_bet.custom_id
        
        if custom_id:
             match_link = f"https://www.sofascore.com/{sport}/match/{slug}/{custom_id}#id:{first_bet.event_id}"
        else:
             match_link = f"https://www.sofascore.com/{slug}/{first_bet.event_id}"

        # Determine Color (Green if profitable in either All-time or Current)
        is_profitable = (user.roi is not None and user.roi > 0) or (user.current_roi is not None and user.current_roi > 0)
        color = 3447003 if is_profitable else 10181046 # Green (0x349933) vs Grey (0x9B9B96)

        # Build Bets Field
        bet_field_lines = []
        for i, bet in enumerate(bets):
            # 🎯 Highlight high confidence or simply the selection
            icon = "🎯" 
            bet_line = f"**{i+1}.** {bet.market_name}: {bet.choice_name} @ **{bet.odds}** {icon}"
            bet_field_lines.append(bet_line)
        
        bets_value = "\n".join(bet_field_lines)

        # Stats Icons
        icon_all = "⚪"
        icon_cur = "🟢" if (user.current_roi and user.current_roi > 10) else "⚪"

        embed = {
            "title": "⚽️ NEW BET ALERT",
            "color": color,
            "fields": [
                {
                    "name": "🔮 Predictor",
                    "value": f"[{user.name}]({user_link})",
                    "inline": True
                },
                {
                    "name": "📊 Performance",
                    "value": (
                        f"**All Time** {icon_all}\n"
                        f"ROI: **{user.roi or 0:.1f}%** | P&L: **{user.profit or 0:+.0f}** | Win: **{user.win_rate or 0:.0f}%**\n\n"
                        f"**Current** {icon_cur}\n"
                        f"ROI: **{user.current_roi or 0:.1f}%** | P&L: **{user.current_profit or 0:+.0f}** | Win: **{user.current_win_rate or 0:.0f}%**"
                    ),
                    "inline": True
                },
                {
                    "name": "⚽️ Match",
                    "value": f"[{first_bet.match_name}]({match_link})",
                    "inline": False
                },
                {
                    "name": f"🎯 Bets ({len(bets)})",
                    "value": bets_value,
                    "inline": False
                }
            ],
            "footer": {
                "text": "Sofascore Monitor • Antigravity",
                # "icon_url": "https://your-logo-url.png" # Placeholder
            },
            "timestamp": datetime.utcnow().isoformat()
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

def send_line_movement_alert(bet: Bet, previous_odds: float, movement_pct: float):
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        # Calculate stats
        direction = "DROP" if bet.odds < previous_odds else "RISE"
        arrow = "🔻" if bet.odds < previous_odds else "🔺"
        color = 15158332 if bet.odds < previous_odds else 3066993 # Red vs Blue/Green? 
        # Actually Drop is usually good for value if you caught it early? 
        # But here we are tracking a tipster's bet. 
        # If odds drop, the tipster's pick is becoming more favorite (market agrees).
        # Value is arguably GONE if you follow now.
        # But user wants to know.
        
        # Link
        # Match Link
        slug = bet.event_slug or "match"
        sport = bet.sport or "sport"
        custom_id = bet.custom_id
        
        if custom_id:
             match_link = f"https://www.sofascore.com/{sport}/match/{slug}/{custom_id}#id:{bet.event_id}"
        else:
             match_link = f"https://www.sofascore.com/{slug}/{bet.event_id}"

        embed = {
            "title": f"{arrow} Line Movement Alert ({movement_pct*100:.1f}%)",
            "color": color,
            "fields": [
                {"name": "Match", "value": f"[{bet.match_name}]({match_link})", "inline": False},
                {"name": "Selection", "value": f"**{bet.market_name}**: {bet.choice_name}", "inline": False},
                {"name": "Odds Change", "value": f"{previous_odds} ➔ **{bet.odds}**", "inline": True},
                {"name": "Movement", "value": f"{direction} of {abs(bet.odds - previous_odds):.2f}", "inline": True},
            ],
            "footer": {"text": "Sofascore Monitor • Line Tracking"}
        }

        payload = {"embeds": [embed]}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)

    except Exception as e:
        logger.error(f"Error sending line movement alert: {e}")

def send_health_alert(status: str, message: str, color: int = 0x00FF00):
   """
   Send system health alerts (Startup, Error, Shutdown).
   Color: Green (0x00FF00) for info, Red (0xFF0000) for errors.
   """
   if not DISCORD_HEALTH_WEBHOOK_URL:
       return

   from datetime import datetime
   embed = {
       "title": f"System Alert: {status}",
       "description": message,
       "color": color,
       "timestamp": datetime.utcnow().isoformat(),
       "footer": {"text": "Sofascore Monitor Health"}
   }
   
   payload = {"embeds": [embed]}
   
   try:
       requests.post(DISCORD_HEALTH_WEBHOOK_URL, json=payload, timeout=5)
   except Exception as e:
       logger.error(f"Failed to send health alert: {e}")

def send_roi_report(stats: dict):
    if not DISCORD_WEBHOOK_URL or not stats:
        return

    try:
        total = stats.get('total_bets', 0)
        wins = stats.get('wins', 0)
        profit = stats.get('profit', 0.0)
        roi = stats.get('roi', 0.0)
        win_rate = stats.get('win_rate', 0.0)

        color = 3447003 if profit > 0 else 10181046 # Green vs Grey
        
        embed = {
            "title": "📈 Monitor ROI Report",
            "color": color,
            "fields": [
                {"name": "Total Prediction Alerts", "value": str(total), "inline": True},
                {"name": "Wins", "value": str(wins), "inline": True},
                {"name": "Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
                {"name": "Total Profit (Units)", "value": f"{profit:+.2f}", "inline": True},
                {"name": "ROI (Yield)", "value": f"**{roi:+.2f}%**", "inline": True},
            ],
            "footer": {"text": "Sofascore Monitor • Performance Tracking"},
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {"embeds": [embed]}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        logger.info(f"Sent ROI Report: {total} bets, {roi:.2f}% ROI")

    except Exception as e:
        logger.error(f"Error sending ROI report: {e}")
