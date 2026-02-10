import sqlite3
import os
from config import DB_PATH
from datetime import datetime

def check_db():
    print(f"Checking DB: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    user_id = "5dadb1036996486450251cb6"
    
    with sqlite3.connect(DB_PATH) as conn:
        # Check User Status
        cursor = conn.execute("SELECT failures, paused_until, last_updated FROM user_status WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            print(f"User Status for {user_id}:")
            print(f"  Failures: {row[0]}")
            print(f"  Paused Until: {row[1]}")
            print(f"  Last Updated: {row[2]}")
            
            if row[1]:
                paused_until = datetime.fromisoformat(str(row[1]))
                if paused_until > datetime.now():
                    print("  ⚠️ USER IS PAUSED!")
        else:
            print(f"User {user_id} not found in user_status table (Has not been checked/failed yet).")

        # Check Seen Bets
        cursor = conn.execute("SELECT count(*) FROM seen_bets WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        print(f"Total Seen Bets for {user_id}: {count}")
        
        # Check specific ID
        bet_id = "DgbsEgb"
        cursor = conn.execute("SELECT created_at FROM seen_bets WHERE id = ?", (bet_id,))
        row = cursor.fetchone()
        if row:
            print(f"✅ Bet {bet_id} IS in DB (Saw at {row[0]})")
        else:
            print(f"❌ Bet {bet_id} is NOT in DB.")

if __name__ == "__main__":
    check_db()
