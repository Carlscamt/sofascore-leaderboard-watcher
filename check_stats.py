import asyncio
import json
from client import SofascoreClient

async def check_stats():
    client = SofascoreClient()
    print("Fetching top predictors...")
    data = await client.get_top_predictors()
    
    if data and 'ranking' in data:
        first_user = data['ranking'][0]
        print(f"User: {first_user.get('nickname')}")
        
        stats = first_user.get('voteStatistics')
        if stats:
            print("--- voteStatistics ---")
            print(json.dumps(stats, indent=2))
        else:
            print("❌ No voteStatistics found.")
    else:
        print("Failed to get ranking data.")

if __name__ == "__main__":
    asyncio.run(check_stats())
