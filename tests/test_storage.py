import pytest
import os
import sqlite3
import uuid
import time
from datetime import datetime, timedelta
from sofascore_monitor.storage import Storage

@pytest.fixture
@pytest.fixture
def db_path(tmp_path):
    # Create a temp file in the pytest temp directory
    d = tmp_path / "data"
    d.mkdir()
    path = d / f"test_{uuid.uuid4()}.db"
    str_path = str(path)
    yield str_path
    # Cleanup is handled by tmp_path, but we can ensure closing if needed
    # (sqlite hooks might prevent deletion if open, but tmp_path usually handles it after test session)
    # If explicit cleanup of WAL files is needed:
    try:
        if os.path.exists(str_path):
            # os.remove(str_path) # Let pytest handle it
            pass
    except PermissionError:
        pass

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

@pytest.mark.asyncio
async def test_add_and_check_seen(storage):
    """Test adding and checking for existing bets."""
    bet_id = "test_bet_1"
    user_id = "user_1"
    
    assert not await storage.is_seen(bet_id)
    
    await storage.add_seen(bet_id, user_id)
    
    assert await storage.is_seen(bet_id)
    
    # Test duplicate insert doesn't crash
    await storage.add_seen(bet_id, user_id)
    assert await storage.is_seen(bet_id)

@pytest.mark.asyncio
async def test_user_failures(storage):
    """Test failure tracking and pausing logic."""
    user_id = "failed_user"
    max_retries = 3
    pause_minutes = 30
    
    # Initial state
    failures, paused_until = await storage.get_user_status(user_id)
    assert failures == 0
    assert paused_until is None
    
    # Increment failure 1
    await storage.increment_failure(user_id, max_retries, pause_minutes)
    failures, paused_until = await storage.get_user_status(user_id)
    assert failures == 1
    assert paused_until is None
    
    # Increment to max
    await storage.increment_failure(user_id, max_retries, pause_minutes) # 2
    await storage.increment_failure(user_id, max_retries, pause_minutes) # 3
    
    failures, paused_until = await storage.get_user_status(user_id)
    assert failures == 3
    assert paused_until is not None
    assert paused_until > datetime.now()

    # Reset
    await storage.reset_failure(user_id)
    failures, paused_until = await storage.get_user_status(user_id)
    assert failures == 0
    assert paused_until is None

# Cleanup old data is synchronous in source code (it calls sync internally or is sync wrapper?)
# Let's check storage.py source again for cleanup_old_data signature.
# Line 136: def cleanup_old_data(self, days: int):
# It is synchronous in the original file I viewed. So no await needed.
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
        
    # We can check via sync method if exposed or just check direct DB or async is_seen
    # storage.is_seen is async, so we need async test if we use it.
    # Let's make this test async to freely use is_seen
    pass

@pytest.mark.asyncio
async def test_cleanup_old_data_async(storage, db_path):
    """Test cleaning up old records."""
    # Insert old record manually
    old_date = datetime.now() - timedelta(days=60)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO seen_bets (id, user_id, created_at) VALUES (?, ?, ?)",
            ("old_bet", "user_1", old_date)
        )
        conn.commit()
        
    assert await storage.is_seen("old_bet")
    
    storage.cleanup_old_data(days=30)
    
    assert not await storage.is_seen("old_bet")
