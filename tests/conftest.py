import pytest
import sqlite3
from pathlib import Path

@pytest.fixture
def test_db(tmp_path):
    """Provide isolated test database with WAL mode enabled (production parity)."""
    db_path = tmp_path / "test_monitor.db"
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    
    return str(db_path)

@pytest.fixture
def storage_layer(test_db):
    """Initialize storage with test DB."""
    from sofascore_monitor.storage import Storage
    storage = Storage(db_path=test_db)
    # Storage init automatically creates tables now
    return storage
