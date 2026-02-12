import pytest
import pytz
from datetime import datetime
from unittest.mock import MagicMock, patch
from sofascore_monitor.monitor import Monitor

@pytest.fixture
def monitor():
    return Monitor(use_auto_discovery=False)

def test_burst_mode_active(monitor):
    # Test cases: 9, 10, 11, 12, 13, 14 should return 60
    # Let's test :09
    mock_now = datetime(2023, 10, 27, 12, 9, 30, tzinfo=pytz.utc)
    
    with patch('sofascore_monitor.monitor.datetime') as mock_dt:
        mock_dt.now.return_value = mock_now
        # We also need utcnow for fallback? logic prefers now(pytz.utc)
        
        interval = monitor.calculate_adaptive_interval(5)
        assert interval == 60, f"Expected 60s at :09, got {interval}"

def test_burst_mode_inactive(monitor):
    # Test cases: 0-8, 15-23, etc.
    # Let's test :00 (Match start) - should be back to normal? 
    # Wait, requirement was "before the start". 
    # Logic: 9 <= rem <= 14. So :00 is rem=0 -> Normal.
    
    mock_now = datetime(2023, 10, 27, 12, 0, 30, tzinfo=pytz.utc)
    
    with patch('sofascore_monitor.monitor.datetime') as mock_dt:
        mock_dt.now.return_value = mock_now
        
        interval = monitor.calculate_adaptive_interval(5)
        assert interval >= 180, f"Expected normal interval (>180) at :00, got {interval}"

def test_manual_check_minutes(monitor):
    # Print what the logic does for 0-15
    print("\nMin | Interval | Mode")
    print("----|----------|-----")
    for m in range(16):
        mock_now = datetime(2023, 10, 27, 12, m, 30, tzinfo=pytz.utc)
        with patch('sofascore_monitor.monitor.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            interval = monitor.calculate_adaptive_interval(5)
            mode = "BURST" if interval == 60 else "Norm"
            print(f":{m:02d} | {interval:4d}s    | {mode}")

if __name__ == "__main__":
    m = Monitor(use_auto_discovery=False)
    test_burst_mode_active(m)
    test_burst_mode_inactive(m)
    test_manual_check_minutes(m)
    print("✅ Tests Passed")
