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
from .notifications import send_discord_alert, send_line_movement_alert, send_health_alert, send_roi_report

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

        # ROI Resolution
        self.last_resolution_check = datetime.now() - timedelta(hours=1) # Run immediately on startup

            
    def calculate_adaptive_interval(self, base_minutes):
        """
        Pure time-based adaptive polling.
        Burst Mode: 60s interval during T-6 to T-1 mins before :00, :15, :30, :45 matches.
        Standard Mode: Base * Multiplier (Weekends 0.8x) +/- 20% Jitter.
        """
        MIN_INTERVAL = 180  # Hard floor for standard mode (3 mins)
        BURST_INTERVAL = 60 # Fast poll for start times

        try:
            # Use UTC as global standard
            now = datetime.now(pytz.utc)
        except Exception:
            now = datetime.utcnow()
            
        current_minute = now.minute
        
        # --- Burst Mode Check ---
        # Matches often start at :00, :15, :30, :45
        # We want to poll frequently in the 5 mins leading up to these (e.g., :09-:14)
        # 15 min cycle: 0-14, 15-29, 30-44, 45-59
        # Check if we are in the last 6 minutes of a 15-min block
        # Modulo 15: 
        # 0..8 -> Normal
        # 9..14 -> Burst (Approaching start time)
        
        rem = current_minute % 15
        if 9 <= rem <= 14:
            # Burst Mode
            # logger.info("Burst Mode Active (Match Start approaching)")
            return BURST_INTERVAL

        # --- Standard Adaptive Mode ---
        # 1. Base Multiplier
        multiplier = 1.0
        
        # Weekend adjustment (Global high traffic)
        # Weekday 5 (Sat), 6 (Sun)
        if now.weekday() >= 5:
            multiplier = 0.8
        
        # 2. Random Jitter (+/- 20%)
        jitter = random.uniform(0.8, 1.2)
        
        interval = int(base_minutes * 60 * multiplier * jitter)
        return max(interval, MIN_INTERVAL)

    async def run(self):
        logger.info("Starting Async Sofascore Monitor (Hardened)...")
        
        # Maintenance on startup
        self.storage.cleanup_old_data(RETENTION_DAYS)

        # Initial Discovery
        if self.use_auto_discovery:
            await self.discover_users()

        msg = f"Monitoring {len(self.users)} users with {SCAN_INTERVAL_MINUTES}m base interval (UTC/Burst Mode Active)."
        logger.info(msg)
        send_health_alert("Service Started", msg, color=0x00FF00)
        
        # Send Initial ROI Report
        roi_stats = await self.storage.get_roi_stats()
        if roi_stats and roi_stats.get('total_bets', 0) > 0:
             send_roi_report(roi_stats)
        
        while True:
            try:
                start_time = datetime.now()
                await self.check_all_users()
                self.last_activity = datetime.now()
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Check Health (Dead Man's Switch logic could go here or external)
                
                # ROI Resolution (Every 1 hour)
                if (datetime.now() - self.last_resolution_check).total_seconds() > 3600:
                    asyncio.create_task(self.resolve_pending_bets())
                    self.last_resolution_check = datetime.now()

                # Adaptive Interval
                sleep_time = self.calculate_adaptive_interval(SCAN_INTERVAL_MINUTES) - elapsed
                
                if sleep_time > 0:
                    mode = "Burst" if sleep_time == 60 else "Adaptive"
                    logger.info(f"Sleeping for {sleep_time:.2f}s ({mode})...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Loop took longer than interval ({elapsed:.2f}s)!")
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                send_health_alert("Service Error", f"Exception in monitor loop: {str(e)}", color=0xFF0000)
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
                # Store for ROI Tracking
                await self.storage.store_alerted_bet(
                    bet_id=b.id,
                    user_id=user.id,
                    event_id=b.event_id,
                    market=b.market_name,
                    selection=b.choice_name,
                    odds=b.odds
                )
    async def resolve_pending_bets(self):
        """Check status of pending bets and update ROI stats."""
        logger.info("Starting ROI Resolution Task...")
        pending = await self.storage.get_pending_bets()
        if not pending:
            logger.info("No pending bets to resolve.")
            return

        # Group by user to minimize requests
        bets_by_user = {}
        for row in pending:
            uid = row['user_id']
            if uid not in bets_by_user:
                bets_by_user[uid] = []
            bets_by_user[uid].append(row)

        for user_id, bets in bets_by_user.items():
            try:
                # Fetch user history (Page 0 should cover recent settled bets)
                # If bets are old, might need page 1, but 1h loop should catch them as they settle.
                data = await self.client.get_user_predictions(user_id, page=0)
                if not data: continue

                predictions = data.get('predictions', [])
                
                # Create a map for fast lookup: event_id -> prediction
                # Also maps event_id+vote to prediction for precise matching
                pred_map = {}
                for p in predictions:
                    eid = p.get('eventId')
                    if eid:
                        pred_map[eid] = p
                        # Also composite key if needed
                        vote = p.get('vote')
                        if vote:
                            pred_map[f"{eid}_{vote}"] = p

                for bet_row in bets:
                    bet_id = bet_row['id']
                    eid = bet_row['event_id']
                    selection = bet_row['selection']
                    
                    # Try to find match
                    # 1. Exact match event_id + selection
                    p = pred_map.get(f"{eid}_{selection}")
                    # 2. Fallback event_id (if selection format matches differently, but usually '1', '2', 'X')
                    if not p:
                        p = pred_map.get(eid)
                        # Check selection match if fallback used
                        if p and str(p.get('vote')) != str(selection):
                            p = None
                    
                    if not p: continue

                    # Check Status
                    status_type = p.get('status', {}).get('type')
                    if status_type == 'finished':
                        correct = p.get('correct') # 1 = Won, -1 = Lost, 0 = Void?
                        # Verify 'correct' values from API debug (1, -1 seen)
                        
                        new_status = 'PENDING'
                        profit = 0.0
                        
                        if correct == 1:
                            new_status = 'WON'
                            odds = bet_row['odds']
                            stake = bet_row['stake']
                            profit = (odds * stake) - stake
                        elif correct == -1:
                            new_status = 'LOST'
                            stake = bet_row['stake']
                            profit = -stake
                        elif correct == 0 or status_type == 'canceled':
                            new_status = 'VOID'
                            profit = 0.0
                        
                        if new_status != 'PENDING':
                            logger.info(f"Bet Resolved: {bet_id} -> {new_status} ({profit:+.2f})")
                            await self.storage.update_bet_outcome(bet_id, new_status, profit)

            except Exception as e:
                logger.error(f"Error resolving bets for user {user_id}: {e}")
                
        logger.info("ROI Resolution Task Completed.")
