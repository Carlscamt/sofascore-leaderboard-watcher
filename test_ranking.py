from client import SofascoreClient
import json

def test_vote_ranking():
    client = SofascoreClient()
    endpoint = "/user-account/vote-ranking"
    
    print(f"Testing endpoint: {endpoint}")
    data = client.fetch(endpoint)
    
    if data:
        print("SUCCESS: Got data!")
        print(json.dumps(data, indent=2)[:2000]) # Print first 2000 chars to see structure
    else:
        print("FAILED: No data returned.")

if __name__ == "__main__":
    test_vote_ranking()
