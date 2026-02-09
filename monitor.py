import asyncio
import logging
import random
from typing import List, Set, Dict
from datetime import datetime, timedelta

# Import local modules
from models import User, Bet
from client import SofascoreClient
from config import TARGET_USERS, POLL_INTERVAL_SECONDS, DB_PATH, MAX_RETRIES, PAUSE_DURATION_MINUTES, RETENTION_DAYS
from storage import Storage
from notifications import send_discord_alert

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
            
    async def run(self):
        logger.info("Starting Async Sofascore Monitor (Hardened)...")
        
        # Maintenance on startup
        self.storage.cleanup_old_data(RETENTION_DAYS)

        # Initial Discovery
        if self.use_auto_discovery:
            await self.discover_users()

        logger.info(f"Monitoring {len(self.users)} users with {POLL_INTERVAL_SECONDS}s base interval.")
        
        while True:
            try:
                start_time = datetime.now()
                await self.check_all_users()
                self.last_activity = datetime.now()
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Check Health (Dead Man's Switch logic could go here or external)
                
                # Jitter sleep
                sleep_time = random.uniform(55, 65) - elapsed
                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Loop took longer than interval ({elapsed:.2f}s)!")
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(60) # Backoff on crash

    async def discover_users(self):
        """Fetch top predictors and add them to the monitoring list."""
        logger.info("Auto-discovering Top Predictors...")
        data = await self.client.get_top_predictors()
        if not data or 'ranking' not in data:
            logger.warning("Failed to fetch top predictors.")
            return

        count = 0
        for row in data['ranking']:
            uid = row.get('id')
            name = row.get('nickname') or row.get('slug') or "Unknown"
            
            if not uid:
                continue
                
            if any(u.id == uid for u in self.users):
                continue
                
            new_user = User(id=uid, name=name, slug=row.get('slug', name))
            self.users.append(new_user)
            count += 1
            
        logger.info(f"Discovered {count} new top predictors.")

    async def check_all_users(self):
        """Concurrent check of all users."""
        tasks = [self.check_user(user) for user in self.users]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
             if isinstance(res, Exception):
                 logger.error(f"Error checking user: {res}")

    async def check_user(self, user: User):
        # 1. Check Rate Limit Status
        failures, paused_until = self.storage.get_user_status(str(user.id))
        if paused_until:
            if datetime.now() < paused_until:
                logger.info(f"Skipping paused user {user.name} until {paused_until}")
                return
            else:
                # Unpause
                self.storage.reset_failure(str(user.id))

        # 2. Fetch Bets
        data = await self.client.get_user_predictions(user.id)
        
        if not data:
            # Increment failure count
            self.storage.increment_failure(str(user.id), MAX_RETRIES, PAUSE_DURATION_MINUTES)
            return
        
        # Reset failures on success
        if failures > 0:
            self.storage.reset_failure(str(user.id))

        predictions = data.get('predictions', []) 
        
        for p in predictions:
            # Bet Parsing Logic
            bet_id = p.get('customId')
            endpoint_id = p.get('id') 
            unique_key = str(bet_id or endpoint_id or f"{p.get('eventId')}_{p.get('vote')}")
            
            # Check DB
            if self.storage.is_seen(unique_key):
                continue
            
            # Use safe float conversion
            try:
                odds_val = p.get('odds', {}).get('decimalValue')
                if odds_val and str(odds_val).replace('.', '', 1).isdigit():
                    odds = float(odds_val)
                else:
                    odds = 0.0
            except (ValueError, TypeError):
                odds = 0.0

            bet = Bet(
                id=unique_key,
                user_id=user.id,
                event_id=p.get('eventId', 0),
                sport=p.get('sportSlug', 'Unknown'),
                market_name="Match Winner", 
                choice_name=p.get('vote', 'Unknown'),
                odds=odds,
                stake=None,
                status=p.get('status', {}).get('description', 'Unknown'),
                created_at=datetime.now()
            )
            
            # Mark as seen in DB
            self.storage.add_seen(unique_key, str(user.id))
            
            # Send Alert
            logger.info(f"New bet found for {user.name}: {bet.choice_name} @ {bet.odds}")
            send_discord_alert(user, bet)
            print(f"[ALERT] {user.name} bet on {bet.choice_name} ({bet.odds})")
