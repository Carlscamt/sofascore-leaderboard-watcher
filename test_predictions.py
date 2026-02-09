from client import SofascoreClient
import json

def test_predictions_with_string_id():
    client = SofascoreClient()
    # ID from the previous output: "678767edb8435cc2d1bba515" (Albert PL)
    user_id = "678767edb8435cc2d1bba515" 
    
    print(f"Testing predictions for user ID: {user_id}")
    
    # Try the standard endpoint first
    data = client.get_user_predictions(user_id)
    
    if data:
        print("SUCCESS: Got predictions!")
        print(json.dumps(data, indent=2)[:500])
    else:
        print("FAILED: Could not get predictions with this ID.")
        
        # Try alternative endpoint for "user-account" based IDs?
        # Maybe /api/v1/user-account/{id}/predictions ?
        endpoint_alt = f"/user-account/{user_id}/predictions"
        print(f"Trying alternative: {endpoint_alt}")
        data_alt = client.fetch(endpoint_alt)
        if data_alt:
             print("SUCCESS: Got predictions with alternative endpoint!")
             print(json.dumps(data_alt, indent=2)[:500])

if __name__ == "__main__":
    test_predictions_with_string_id()
