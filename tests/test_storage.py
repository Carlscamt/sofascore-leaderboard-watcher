import pytest
import os
import sqlite3
import uuid
import time
from datetime import datetime, timedelta
from storage import Storage

@pytest.fixture
def db_path():
    path = f"test_{uuid.uuid4()}.db"
    yield path
    # Cleanup with retry for Windows file locking
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            if os.path.exists(f"{path}-shm"):
                os.remove(f"{path}-shm")
            if os.path.exists(f"{path}-wal"):
                os.remove(f"{path}-wal")
            break
        except PermissionError:
            time.sleep(0.1)

@pytest.fixture
def storage(db_path):
    storage = Storage(db_path)
    return storage

def test_init_db(storage, db_path):
    """Test that tables are created correctly."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "seen_bets" in tables
        assert "user_status" in tables

def test_add_and_check_seen(storage):
    """Test adding and checking for existing bets."""
    bet_id = "test_bet_1"
    user_id = "user_1"
    
    assert not storage.is_seen(bet_id)
    
    storage.add_seen(bet_id, user_id)
    
    assert storage.is_seen(bet_id)
    
    # Test duplicate insert doesn't crash
    storage.add_seen(bet_id, user_id)
    assert storage.is_seen(bet_id)

def test_user_failures(storage):
    """Test failure tracking and pausing logic."""
    user_id = "failed_user"
    max_retries = 3
    pause_minutes = 30
    
    # Initial state
    failures, paused_until = storage.get_user_status(user_id)
    assert failures == 0
    assert paused_until is None
    
    # Increment failure 1
    storage.increment_failure(user_id, max_retries, pause_minutes)
    failures, paused_until = storage.get_user_status(user_id)
    assert failures == 1
    assert paused_until is None
    
    # Increment to max
    storage.increment_failure(user_id, max_retries, pause_minutes) # 2
    storage.increment_failure(user_id, max_retries, pause_minutes) # 3
    
    failures, paused_until = storage.get_user_status(user_id)
    assert failures == 3
    assert paused_until is not None
    assert paused_until > datetime.now()

    # Reset
    storage.reset_failure(user_id)
    failures, paused_until = storage.get_user_status(user_id)
    assert failures == 0
    assert paused_until is None

def test_cleanup_old_data(storage, db_path):
    """Test cleaning up old records."""
    # Insert old record manually
    old_date = datetime.now() - timedelta(days=60)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO seen_bets (id, user_id, created_at) VALUES (?, ?, ?)",
            ("old_bet", "user_1", old_date)
        )
        conn.commit()
        
    assert storage.is_seen("old_bet")
    
    storage.cleanup_old_data(days=30)
    
    assert not storage.is_seen("old_bet")
