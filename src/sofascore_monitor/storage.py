import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, db_path: str = "sofascore_monitor.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Helper to get connection with timeout and WAL mode."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL;")
                
                # Seen bets table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS seen_bets (
                        id TEXT PRIMARY KEY,
                        user_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Index for faster lookups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_bets_user ON seen_bets(user_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_bets_created ON seen_bets(created_at);")

                # User status table for rate limiting
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_status (
                        user_id TEXT PRIMARY KEY,
                        failures INTEGER DEFAULT 0,
                        paused_until TIMESTAMP,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Line Movement Tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS latest_odds (
                        bet_id TEXT PRIMARY KEY,
                        odds REAL NOT NULL,
                        previous_odds REAL,
                        updated_at INTEGER NOT NULL,
                        alert_sent INTEGER DEFAULT 0
                    ) WITHOUT ROWID
                """)
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init DB: {e}")

    async def is_seen(self, bet_id: str) -> bool:
        return await asyncio.to_thread(self._is_seen_sync, bet_id)

    def _is_seen_sync(self, bet_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT 1 FROM seen_bets WHERE id = ?", (bet_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking seen bet: {e}")
            return False

    async def add_seen(self, bet_id: str, user_id: str):
        await asyncio.to_thread(self._add_seen_sync, bet_id, user_id)

    def _add_seen_sync(self, bet_id: str, user_id: str):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_bets (id, user_id) VALUES (?, ?)",
                    (bet_id, user_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding seen bet: {e}")

    async def get_user_status(self, user_id: str) -> Tuple[int, Optional[datetime]]:
        return await asyncio.to_thread(self._get_user_status_sync, user_id)

    def _get_user_status_sync(self, user_id: str) -> Tuple[int, Optional[datetime]]:
        """Return (failures, paused_until)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT failures, paused_until FROM user_status WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    failures = row[0]
                    paused_until = datetime.fromisoformat(row[1]) if row[1] else None
                    return failures, paused_until
                return 0, None
        except Exception as e:
            logger.error(f"Error getting user status: {e}")
            return 0, None

    async def increment_failure(self, user_id: str, max_retries: int, pause_minutes: int):
        await asyncio.to_thread(self._increment_failure_sync, user_id, max_retries, pause_minutes)

    def _increment_failure_sync(self, user_id: str, max_retries: int, pause_minutes: int):
        try:
            with self._get_connection() as conn:
                # Get current failures
                cursor = conn.execute("SELECT failures FROM user_status WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                failures = (row[0] if row else 0) + 1
                
                paused_until = None
                if failures >= max_retries:
                    paused_until = datetime.now() + timedelta(minutes=pause_minutes)
                    logger.warning(f"Pausing user {user_id} for {pause_minutes}m due to {failures} failures.")

                conn.execute("""
                    INSERT INTO user_status (user_id, failures, paused_until, last_updated)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        failures = ?,
                        paused_until = ?,
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id, failures, paused_until, failures, paused_until))
                conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing failure: {e}")

    async def reset_failure(self, user_id: str):
        await asyncio.to_thread(self._reset_failure_sync, user_id)

    def _reset_failure_sync(self, user_id: str):
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO user_status (user_id, failures, paused_until, last_updated)
                    VALUES (?, 0, NULL, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        failures = 0,
                        paused_until = NULL,
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error resetting failure: {e}")

    def cleanup_old_data(self, days: int):
        try:
            cutoff_dt = datetime.now() - timedelta(days=days)
            cutoff_ts = int(cutoff_dt.timestamp())
            
            with self._get_connection() as conn:
                conn.execute("DELETE FROM seen_bets WHERE created_at < ?", (cutoff_dt,))
                conn.execute("DELETE FROM latest_odds WHERE updated_at < ?", (cutoff_ts,))
                conn.commit()
            logger.info(f"Cleaned up bets/odds older than {days} days.")
        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")

    # Helper for batch loading if needed, keeping sync for now or can wrap
    def get_user_seen_bets(self, user_id: str) -> Set[str]:
        """Load all seen bets for a user into a set."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT id FROM seen_bets WHERE user_id = ?", (user_id,))
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error loading user bets: {e}")
            return set()

    # --- Line Movement Tracking ---

    async def get_odds_snapshot(self, bet_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self._get_odds_snapshot_sync, bet_id)

    def _get_odds_snapshot_sync(self, bet_id: str) -> Optional[dict]:
        try:
            with self._get_connection() as conn:
                # Use row factory for dict
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM latest_odds WHERE bet_id = ?", (bet_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting odds snapshot: {e}")
            return None

    async def upsert_odds_snapshot(self, bet_id: str, odds: float, previous_odds: Optional[float]):
        await asyncio.to_thread(self._upsert_odds_snapshot_sync, bet_id, odds, previous_odds)

    def _upsert_odds_snapshot_sync(self, bet_id: str, odds: float, previous_odds: Optional[float]):
        try:
            updated_at = int(datetime.now().timestamp())
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO latest_odds (bet_id, odds, previous_odds, updated_at, alert_sent)
                    VALUES (?, ?, ?, ?, 0)
                    ON CONFLICT(bet_id) DO UPDATE SET
                        odds = excluded.odds,
                        previous_odds = excluded.previous_odds,
                        updated_at = excluded.updated_at
                        -- alert_sent is preserved? No, logic says separate update.
                        -- Actually, if we upsert, we might want to preserve alert_sent unless explicitly reset?
                        -- If we use 'DO UPDATE SET ...', fields not mentioned are preserved IF they existed?
                        -- No, 'alert_sent' is omitted in SET list -> preserved?
                        -- Wait, if row exists, we update odds/prev/updated_at. alert_sent remains whatever it was. Correct.
                """, (bet_id, odds, previous_odds, updated_at))
                conn.commit()
        except Exception as e:
            logger.error(f"Error upserting odds snapshot: {e}")
            
    async def mark_alert_sent(self, bet_id: str):
        await asyncio.to_thread(self._set_alert_flag_sync, bet_id, 1)

    async def reset_alert_flag(self, bet_id: str):
        await asyncio.to_thread(self._set_alert_flag_sync, bet_id, 0)
        
    def _set_alert_flag_sync(self, bet_id: str, flag: int):
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE latest_odds SET alert_sent = ? WHERE bet_id = ?", (flag, bet_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error setting alert flag: {e}")
