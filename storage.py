import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, Optional, Tuple

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, db_path: str = "sofascore_monitor.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init DB: {e}")

    def is_seen(self, bet_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT 1 FROM seen_bets WHERE id = ?", (bet_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking seen bet: {e}")
            return False

    def add_seen(self, bet_id: str, user_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_bets (id, user_id) VALUES (?, ?)",
                    (bet_id, user_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding seen bet: {e}")

    def get_user_status(self, user_id: str) -> Tuple[int, Optional[datetime]]:
        """Return (failures, paused_until)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
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

    def increment_failure(self, user_id: str, max_retries: int, pause_minutes: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
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

    def reset_failure(self, user_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
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
            cutoff = datetime.now() - timedelta(days=days)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM seen_bets WHERE created_at < ?", (cutoff,))
                conn.commit()
            logger.info(f"Cleaned up bets older than {days} days.")
        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")

    def get_user_seen_bets(self, user_id: str) -> Set[str]:
        """Load all seen bets for a user into a set."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT id FROM seen_bets WHERE user_id = ?", (user_id,))
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error loading user bets: {e}")
            return set()
