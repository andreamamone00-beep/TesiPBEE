import requests
import json

# Test the API endpoint directly
url = "http://127.0.0.1:5000/api/dataset"
params = {
    "dataset": "dataset2",
    "format": "all",
    "method": "all",
    "source": "all",
    "res_max": "3.5"
}

print(f"Testing API call to: {url}")
print(f"Parameters: {params}")
print()

try:
    response = requests.get(url, params=params)
    print(f"Status code: {response.status_code}")
    print(f"Response headers: {response.headers}")
    print()
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success! Got {len(data.get('records', []))} records")
        print(f"Dataset: {data.get('dataset')}")
        print(f"First record: {json.dumps(data.get('records', [{}])[0], indent=2)}")
    else:
        print(f"Error response: {response.text}")
        
except Exception as e:
    print(f"Exception occurred: {e}")
    import traceback
    traceback.print_exc()
