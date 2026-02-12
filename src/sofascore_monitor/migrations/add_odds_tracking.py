import sqlite3
import sys
from pathlib import Path

# Add project root to path to import config if needed, or just hardcode DB name for now
# Assuming runs from project root
DB_PATH = "data/sofascore_monitor.db"

def migrate_odds_tracking(db_path):
    """Add latest_odds table for line movement tracking"""
    print(f"Migrating database at {db_path}...")
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS latest_odds (
                bet_id TEXT PRIMARY KEY,
                odds REAL NOT NULL,
                previous_odds REAL,
                updated_at INTEGER NOT NULL,
                alert_sent INTEGER DEFAULT 0
            ) WITHOUT ROWID
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_updated 
            ON latest_odds(updated_at)
        """)
        
        print("✅ Migration successful: 'latest_odds' table created.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        conn.commit()
        conn.close()

if __name__ == "__main__":
    path = DB_PATH
    if len(sys.argv) > 1:
        path = sys.argv[1]
    migrate_odds_tracking(path)
