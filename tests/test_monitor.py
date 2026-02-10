import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from monitor import Monitor
from models import User, Bet

@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client

@pytest.fixture
def mock_storage():
    storage = MagicMock()
    return storage

@pytest.fixture
def monitor(mock_client, mock_storage):
    with patch('monitor.SofascoreClient', return_value=mock_client), \
         patch('monitor.Storage', return_value=mock_storage):
        monitor = Monitor(use_auto_discovery=False)
        monitor.users = [User(id="123", name="Test User", slug="test-user")]
        return monitor

@pytest.mark.asyncio
async def test_discover_users(monitor):
    """Test auto-discovery adds new users."""
    monitor.client.get_top_predictors.return_value = {
        "ranking": [
            {"id": 456, "nickname": "New User", "slug": "new-user"},
            {"id": 123, "nickname": "Test User", "slug": "test-user"} # Existing
        ]
    }
    
    await monitor.discover_users()
    
    assert len(monitor.users) == 2
    assert monitor.users[1].id == "456"
    assert monitor.users[1].name == "New User"

@pytest.mark.asyncio
async def test_discover_users_limit(monitor):
    """Test that auto-discovery respects the limit."""
    # Mock return with many users
    monitor.client.get_top_predictors.return_value = {
        "ranking": [{"id": i, "nickname": f"User {i}"} for i in range(20)]
    }
    
    # We need to patch config.TOP_PREDICTORS_LIMIT, but it's imported into monitor module
    # So we patch monitor.TOP_PREDICTORS_LIMIT
    with patch('monitor.TOP_PREDICTORS_LIMIT', 5):
        await monitor.discover_users()
        
    # Should only have 1 (from init) + 5 discovered
    assert len(monitor.users) == 1 + 5

@pytest.mark.asyncio
async def test_check_user_paused(monitor):
    """Test that paused users are skipped."""
    # Mock storage to return paused status
    monitor.storage.get_user_status.return_value = (3, datetime.now() + timedelta(minutes=30))
    
    await monitor.check_user(monitor.users[0])
    
    # Verify client was NOT called
    monitor.client.get_user_predictions.assert_not_called()

@pytest.mark.asyncio
async def test_check_user_generic_failure(monitor):
    """Test that generic API failure increments failure count but DOES NOT PAUSE."""
    monitor.storage.get_user_status.return_value = (0, None)
    monitor.client.get_user_predictions.return_value = None # Simulate generic failure
    
    await monitor.check_user(monitor.users[0])
    
    # Called with 0 minutes pause
    monitor.storage.increment_failure.assert_called_with(str(monitor.users[0].id), 3, 0)

@pytest.mark.asyncio
async def test_check_user_404_failure(monitor):
    """Test that 404 failure increments failure count AND PAUSES."""
    monitor.storage.get_user_status.return_value = (0, None)
    # Simulate 404
    from client import UserNotFoundError
    monitor.client.get_user_predictions.side_effect = UserNotFoundError("404")
    
    await monitor.check_user(monitor.users[0])
    
    # Called with 30 minutes pause
    monitor.storage.increment_failure.assert_called_with(str(monitor.users[0].id), 3, 30)

@pytest.mark.asyncio
async def test_new_bet_alert(monitor):
    """Test that a new bet triggers an alert."""
    monitor.storage.get_user_status.return_value = (0, None)
    monitor.client.get_user_predictions.return_value = {
        "predictions": [{
            "id": 999,
            "eventId": 555,
            "vote": "1",
            "odds": {"decimalValue": "1.50"},
            "sportSlug": "tennis",
            "market_name": "Match Winner", 
            "choice_name": "1",
            "status": {"description": "Pending"}
        }]
    }
    # Simulate not seen in DB
    monitor.storage.is_seen.return_value = False
    
    with patch('monitor.send_discord_alert') as mock_alert:
        await monitor.check_user(monitor.users[0])
        
        # Verify DB add
        monitor.storage.add_seen.assert_called_once()
        # Verify Alert
        mock_alert.assert_called_once()
        args, _ = mock_alert.call_args
        assert args[0].id == "123"
        assert args[1].id == "999"
