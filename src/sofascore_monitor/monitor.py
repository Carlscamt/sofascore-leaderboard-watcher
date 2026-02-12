import asyncio
import logging
import random
import pytz
from typing import List, Set, Dict
from datetime import datetime, timedelta

# Import local modules
from .models import User, Bet
from .client import SofascoreClient, UserNotFoundError
from .config import (
    TARGET_USERS, 
    POLL_INTERVAL_SECONDS,
    SCAN_INTERVAL_MINUTES, 
    DB_PATH, 
    MAX_RETRIES, 
    PAUSE_DURATION_MINUTES, 
    RETENTION_DAYS, 
    TOP_PREDICTORS_LIMIT,
    MIN_ROI,
    MIN_AVG_ODDS,
    MIN_TOTAL_BETS,
    MIN_WIN_RATE,
    TIME_LOOKAHEAD_HOURS,
    MATCH_GRACE_PERIOD_MINUTES
)
from .storage import Storage
from .notifications import send_discord_alert, send_line_movement_alert

logger = logging.getLogger(__name__)

class Monitor:
    def __init__(self, use_auto_discovery=True):
        self.client = SofascoreClient()
        self.storage = Storage(DB_PATH)
        self.use_auto_discovery = use_auto_discovery
        self.users: List[User] = []
        self.last_activity = datetime.now()
        
        # Load static users from config
        for u in TARGET_USERS:
            self.users.append(User(**u))
            
        # Resource Bounding
        self.http_semaphore = asyncio.BoundedSemaphore(5)
            
    def calculate_adaptive_interval(self, base_minutes):
        """
        Pure time-based adaptive polling.
        Returns: seconds to sleep before next poll.
        """
        MIN_INTERVAL = 180  # Hard floor: 3 minutes minimum
        
        try:
            # Use London time as proxy for Sofascore activity
            now = datetime.now(pytz.timezone('Europe/London'))
        except Exception:
            now = datetime.now()
            
        hour = now.hour
        
        if 18 <= hour <= 23:  # Peak betting
            multiplier = random.uniform(0.7, 1.0)
        elif 0 <= hour <= 6:  # Late night
            multiplier = random.uniform(2.0, 3.0)
        else:  # Business hours
            multiplier = random.uniform(0.9, 1.4)
        
        # Weekend adjustment
        if now.weekday() >= 5:
            multiplier *= 0.85
        
        interval = int(base_minutes * 60 * multiplier)
        return max(interval, MIN_INTERVAL)

    async def run(self):
        logger.info("Starting Async Sofascore Monitor (Hardened)...")
        
        # Maintenance on startup
        self.storage.cleanup_old_data(RETENTION_DAYS)

        # Initial Discovery
        if self.use_auto_discovery:
            await self.discover_users()

        logger.info(f"Monitoring {len(self.users)} users with {SCAN_INTERVAL_MINUTES}m base interval.")
        
        while True:
            try:
                start_time = datetime.now()
                await self.check_all_users()
                self.last_activity = datetime.now()
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Check Health (Dead Man's Switch logic could go here or external)
                
                # Adaptive Interval
                sleep_time = self.calculate_adaptive_interval(SCAN_INTERVAL_MINUTES) - elapsed
                
                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time:.2f}s (Adaptive)...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Loop took longer than interval ({elapsed:.2f}s)!")
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(60) # Backoff on crash

    async def discover_users(self):
        """Fetch top predictors and add them to the monitoring list."""
        logger.info(f"Auto-discovering Top {TOP_PREDICTORS_LIMIT} Predictors...")
        data = await self.client.get_top_predictors()
        if not data or 'ranking' not in data:
            logger.warning("Failed to fetch top predictors.")
            return

        count = 0
        for row in data['ranking']:
            if count >= TOP_PREDICTORS_LIMIT:
                break

            uid = str(row.get('id'))
            name = row.get('nickname') or row.get('slug') or "Unknown"
            
            if not uid:
                continue
                
            if any(u.id == uid for u in self.users):
                continue
                
            # Extract Stats
            # JSON 'roi' = Profit (Units). 'percentage' = Win Rate. Real ROI must be calculated.
            roi_percent = 0.0
            profit_units = 0.0
            win_rate_val = 0.0
            
            stats = row.get('voteStatistics', {}).get('allTime', {})
            if stats:
                # Profit
                profit_units = float(stats.get('roi', 0.0) or 0.0)
                
                # Win Rate
                wr_str = stats.get('percentage', '0').replace('%', '')
                if wr_str.isdigit() or wr_str.replace('.', '', 1).isdigit():
                    win_rate_val = float(wr_str)
                
                # ROI (Yield) = Profit / Total Bets * 100 (assuming flat stakes)
                total_bets = 0
                total_str = str(stats.get('total', '0'))
                if total_str.isdigit():
                    total_bets = int(total_str)
                
                if total_bets > 0:
                    roi_percent = (profit_units / total_bets) * 100

            # --- User Filtering ---
            # 1. Min ROI
            if roi_percent < MIN_ROI:
                # logger.debug(f"Skipping {name}: ROI {roi_percent:.1f}% < {MIN_ROI}%")
                continue
                
            # 2. Min Total Bets
            if total_bets < MIN_TOTAL_BETS:
                # logger.debug(f"Skipping {name}: Bets {total_bets} < {MIN_TOTAL_BETS}")
                continue
                
            # 3. Min Avg Odds (Check if available in stats?)
            # stats['avgCorrectOdds'] exists but strictly avg odds for ALL bets might not be there directly
            # We can use avgCorrectOdds as a proxy or skip if strictly needed.
            # But the requirement was "Avg Odds". 
            # Often 'voteStatistics' has 'avgOdds'. Let's check previous inspection?
            # It had "avgCorrectOdds": {"decimalValue": "2.11"...}
            # Iterate and check? 
            # For now, let's use avgCorrectOdds if available or just proceed. 
            # API inspection showed: 
            # "avgCorrectOdds": {...}
            # It didn't show "avgOdds" for all bets.
            # Use avgCorrectOdds for filtering? Or skip for now?
            # User asked for "filters for... avg odds". 
            # Let's try to parse 'avgCorrectOdds'
            avg_odds = 0.0
            aco = stats.get('avgCorrectOdds', {})
            if aco:
                 val = aco.get('decimalValue')
                 if val:
                     try:
                         avg_odds = float(val)
                     except: pass
            
            if avg_odds < MIN_AVG_ODDS:
                 # logger.debug(f"Skipping {name}: AvgOdds {avg_odds} < {MIN_AVG_ODDS}")
                 continue

            # --- User Filtering End ---

            # Extract Current Stats
            cur_roi = 0.0
            cur_profit = 0.0
            cur_wr = 0.0
            
            cur_stats = row.get('voteStatistics', {}).get('current', {})
            if cur_stats:
                cur_profit = float(cur_stats.get('roi', 0.0) or 0.0)
                
                cwr_str = cur_stats.get('percentage', '0').replace('%', '')
                if cwr_str.isdigit() or cwr_str.replace('.', '', 1).isdigit():
                    cur_wr = float(cwr_str)
                    
                cur_total = 0
                ct_str = str(cur_stats.get('total', '0'))
                if ct_str.isdigit():
                    cur_total = int(ct_str)
                    
                if cur_total > 0:
                    cur_roi = (cur_profit / cur_total) * 100

            new_user = User(
                id=uid, 
                name=name, 
                slug=row.get('slug', name),
                roi=roi_percent,
                profit=profit_units,
                win_rate=win_rate_val,
                current_roi=cur_roi,
                current_profit=cur_profit,
                current_win_rate=cur_wr
            )
            self.users.append(new_user)
            count += 1
            
        logger.info(f"Discovered {count} new top predictors.")



    async def check_line_movement(self, bet: Bet):
        if not bet.odds or bet.odds <= 1.0: return

        snapshot = await self.storage.get_odds_snapshot(bet.id)
        previous_odds = snapshot['odds'] if snapshot else None
        
        if previous_odds and previous_odds > 1.0:
            diff = abs(bet.odds - previous_odds)
            movement_pct = diff / previous_odds
            
            if movement_pct >= 0.15:
                # Significant movement
                alert_sent = snapshot.get('alert_sent', 0)
                if not alert_sent:
                    logger.info(f"Line Movement! {bet.match_name}: {previous_odds} -> {bet.odds}")
                    send_line_movement_alert(bet, previous_odds, movement_pct)
                    await self.storage.mark_alert_sent(bet.id)
            else:
                # Normalized - reset flag if set
                if snapshot.get('alert_sent'):
                     await self.storage.reset_alert_flag(bet.id)
        
        # Always update snapshot
        await self.storage.upsert_odds_snapshot(bet.id, bet.odds, previous_odds)

    async def check_all_users(self):
        """Concurrent check of all users."""
        tasks = [self.check_user(user) for user in self.users]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
             if isinstance(res, Exception):
                 logger.error(f"Error checking user: {res}")

    async def check_user(self, user: User):
        # 1. Check Rate Limit Status
        failures, paused_until = await self.storage.get_user_status(str(user.id))
        if paused_until:
            if datetime.now() < paused_until:
                # logger.info(f"Skipping paused user {user.name} until {paused_until}")
                return
            else:
                # Unpause
                await self.storage.reset_failure(str(user.id))

        # 2. Fetch Bets
        try:
            async with self.http_semaphore:
                data = await self.client.get_user_predictions(user.id)
        except UserNotFoundError:
            logger.warning(f"User {user.name} (404) not found. Pausing.")
            # 404 -> Trigger Long Pause
            await self.storage.increment_failure(str(user.id), MAX_RETRIES, PAUSE_DURATION_MINUTES)
            return

        if not data:
            # Other error -> Increment failure but DO NOT PAUSE (0 mins)
            await self.storage.increment_failure(str(user.id), MAX_RETRIES, 0)
            return
        
        # Reset failures on success
        if failures > 0:
            await self.storage.reset_failure(str(user.id))

        predictions = data.get('predictions', []) 
        bets_by_match = {}
        
        for p in predictions:
            # Bet Parsing Logic
            match_custom_id = p.get('customId')
            endpoint_id = p.get('id') 
            unique_key = str(endpoint_id or f"{p.get('eventId')}_{p.get('vote')}")

            # Get correct event slug
            event_slug = p.get('eventSlug')
            if not event_slug:
                h = p.get('homeTeamName', 'event').lower().replace(' ', '-')
                a = p.get('awayTeamName', '').lower().replace(' ', '-')
                event_slug = f"{h}-{a}" if a else h
            
            # Check Status - Skip if match is already finished
            status_type = p.get('status', {}).get('type')
            if status_type == 'finished':
                await self.storage.add_seen(unique_key, str(user.id))
                continue

            # Time Filtering
            start_timestamp = p.get('startDateTimestamp')
            start_time = None
            if start_timestamp:
                start_time = datetime.fromtimestamp(start_timestamp)
                now = datetime.now()
                
                # 1. 24-Hour Lookahead Limit
                if start_time > now + timedelta(hours=TIME_LOOKAHEAD_HOURS):
                    continue

                # 2. Started Match Limit (Max 5 mins grace)
                if start_time < now:
                    if now - start_time > timedelta(minutes=MATCH_GRACE_PERIOD_MINUTES):
                        await self.storage.add_seen(unique_key, str(user.id)) # suppress
                        continue

            # Parse Odds (moved up)
            try:
                odds_val = p.get('odds', {}).get('decimalValue')
                if odds_val and str(odds_val).replace('.', '', 1).isdigit():
                    odds = float(odds_val)
                else:
                    odds = 0.0
            except (ValueError, TypeError):
                odds = 0.0

            # Create Bet Object Early
            bet = Bet(
                id=unique_key,
                user_id=user.id,
                event_id=p.get('eventId', 0),
                event_slug=event_slug,
                custom_id=match_custom_id,
                sport=p.get('sportSlug', 'Unknown'),
                match_name=f"{p.get('homeTeamName', 'Unknown')} vs {p.get('awayTeamName', 'Unknown')}",
                market_name="Match Winner", 
                choice_name=p.get('vote', 'Unknown'),
                odds=odds,
                stake=None,
                status=p.get('status', {}).get('description', 'Unknown'),
                start_time=start_time,
                created_at=datetime.now()
            )
            
            # Check Line Movement (Always run for active bets)
            await self.check_line_movement(bet)

            # Check Is Seen (New Bet Alert Filter)
            if await self.storage.is_seen(unique_key):
                continue
            
            # Mark as seen in DB
            await self.storage.add_seen(unique_key, str(user.id))
            
            # Group by Event ID
            eid = bet.event_id
            if eid not in bets_by_match:
                bets_by_match[eid] = []
            bets_by_match[eid].append(bet)
            
        # Send Grouped Alerts
        for eid, bets in bets_by_match.items():
            if not bets: continue
            
            logger.info(f"Sending grouped alert for {user.name}: {len(bets)} bets on match {eid}")
            send_discord_alert(user, bets)
            for b in bets:
                print(f"[ALERT] {user.name} bet on {b.match_name} ({b.market_name}: {b.choice_name})")
