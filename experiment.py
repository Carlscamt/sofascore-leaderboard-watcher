import sys
import os
import json
import logging
import importlib.util
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import src/scraper.py directly to avoid conflict with src/scraper/ package
scraper_path = project_root / "src" / "scraper.py"
spec = importlib.util.spec_from_file_location("scraper_module", scraper_path)
scraper_module = importlib.util.module_from_spec(spec)
sys.modules["scraper_module"] = scraper_module
spec.loader.exec_module(scraper_module)

fetch_json = scraper_module.fetch_json

def test_endpoint(endpoint, description):
    logger.info(f"Testing {description}: {endpoint}")
    # Force cache_ttl=0 to avoid using old cache
    data = fetch_json(endpoint, retries=1, cache_ttl=0)
    if data:
        logger.info(f"SUCCESS: Got data for {endpoint}")
        # Print a snippet of data
        print(f"Data for {endpoint}:")
        print(json.dumps(data, indent=2)[:500])
        return data
    else:
        logger.error(f"FAILED: No data for {endpoint}")
        return None

def run_tests():
    # 1. Test basic connectivity
    # test_endpoint("/sport/tennis/scheduled-events/2024-05-20", "Basic Schedule (Historical)")

    # 2. Test Leaderboard Endpoints
    # Try probable endpoints for "Top Predictors"
    # Note: These are guesses based on "sofa-editor" or "user" paths.
    
    # Try looking for a specific user first if we can't find the list.
    # But let's try the list first.
    # Often "top-predictors" is under /sport/football/... or /category/...
    # or /user/rankings
    
    # Let's try to get a user profile from a known ID if possible, or guess one.
    # If the user has provided a link: https://www.sofascore.com/user/top-predictors
    # The API might be:
    test_endpoint("/user/top-predictors", "User Top Predictors")
    test_endpoint("/sofa-editor/top-predictors", "Sofa Editor Top Predictors")
    
    # Maybe try a random user ID if we can guess one? 
    # Or try to search for users?
    # endpoint /search/all?q=... might return users?
    test_endpoint("/search/all?q=prediction", "Search for users/predictors")

if __name__ == "__main__":
    run_tests()
