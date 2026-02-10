import asyncio
import json
import logging
from client import SofascoreClient

logging.basicConfig(level=logging.INFO)

async def debug_user():
    client = SofascoreClient()
    user_id = "5dadb1036996486450251cb6"
    
    print(f"Fetching predictions for user: {user_id}")
    data = await client.get_user_predictions(user_id)
    
    if not data:
        print("❌ No data returned from API.")
        return

    predictions = data.get('predictions', [])
    print(f"✅ Found {len(predictions)} predictions.")
    
    if predictions:
        print("--- First Prediction Structure ---")
        p = predictions[0]
        ts = p.get('startDateTimestamp')
        import datetime
        if ts:
            dt = datetime.datetime.fromtimestamp(ts)
            print(f"Date: {dt} (Timestamp: {ts})")
        
        print(json.dumps(p, indent=2))
        
    print(f"✅ Found {len(predictions)} predictions total.")

    print("\nChecking Leaderboard Rank...")
    leaderboard = await client.get_top_predictors()
    rank = -1
    if leaderboard and 'ranking' in leaderboard:
        item = next((r for r in leaderboard['ranking'] if str(r.get('id')) == user_id), None)
        if item:
             rank = leaderboard['ranking'].index(item) + 1
             print(f"✅ User found at Rank #{rank}")
        else:
             print("❌ User NOT found in the top leaderboard list fetched.")
    else:
        print("❌ Failed to fetch leaderboard.")

if __name__ == "__main__":
    asyncio.run(debug_user())
