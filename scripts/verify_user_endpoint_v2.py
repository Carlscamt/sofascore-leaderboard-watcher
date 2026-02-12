import sys
import os
import asyncio
import json
from pathlib import Path

current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
sys.path.append(str(project_root / "src"))

from sofascore_monitor.client import SofascoreClient

async def verify():
    client = SofascoreClient()
    print("Fetching top predictors to get an ID...")
    data = await client.get_top_predictors()
    
    if data and 'ranking' in data and len(data['ranking']) > 0:
        user_id = data['ranking'][0]['id']
        print(f"Testing with User ID: {user_id}")
        
        # Test 1: /user-account/{id}
        endpoint1 = f"/user-account/{user_id}"
        print(f"\nFetching {endpoint1}...")
        res1 = await client.fetch(endpoint1)
        if res1:
             print("✅ Success!")
             print(list(res1.keys()))
             # Check for stats inside
             if 'voteStatistics' in res1:
                 print("Found 'voteStatistics'")
        else:
            print("❌ Failed.")

        # Test 2: /user/{id}/statistics
        endpoint2 = f"/user/{user_id}/statistics"
        print(f"\nFetching {endpoint2}...")
        res2 = await client.fetch(endpoint2)
        if res2:
             print("✅ Success!")
             print(list(res2.keys()))
        else:
            print("❌ Failed.")

if __name__ == "__main__":
    asyncio.run(verify())
