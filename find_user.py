from client import SofascoreClient
import json

def find_users():
    client = SofascoreClient()
    queries = ["sofa", "editor", "predictor", "expert", "tips", "bet"]
    
    print("Searching for potential users...")
    
    for q in queries:
        print(f"Query: {q}")
        data = client.search(q)
        if data and 'results' in data:
            for result in data['results']:
                entity = result.get('entity', {})
                type_ = result.get('type', '')
                print(f"  Found: {type_} - {entity.get('name')} (ID: {entity.get('id')})")
                
                # If we find a 'user' or 'editor' type, that's gold.
                if type_ in ['user', 'editor', 'human']: # Check valid types
                     print(f"!!! FOUND USER CANDIDATE: {entity.get('name')} ID: {entity.get('id')}")

if __name__ == "__main__":
    find_users()
