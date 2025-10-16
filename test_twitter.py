import os
import requests
import json
import sys

# Get environment variables
API_KEY = os.getenv('TWITTERAPI_IO_KEY')
USERNAME = os.getenv('USERNAME')

# Validate inputs
if not API_KEY:
    raise ValueError('Missing TWITTERAPI_IO_KEY')
if not USERNAME:
    raise ValueError('Missing username')

# API call
url = f'https://api.twitterapi.io/twitter/user/last_tweets?userName={USERNAME}'
headers = {'X-API-Key': API_KEY}

try:
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Full Response: {json.dumps(response.json(), indent=2)}")  # Pretty-print JSON for logs
    
    response.raise_for_status()  # Raises an HTTPError for bad responses
    data = response.json()
    
    # Extract tweet IDs safely
    tweets = data.get('tweets', [])
    tweet_ids = [t['id'] for t in tweets if isinstance(t, dict) and 'id' in t]
    
    if not tweet_ids:
        print('⚠️ No tweet IDs found for this user.')
    else:
        print('✅ Tweet IDs:', tweet_ids)
        
except requests.exceptions.RequestException as e:
    print(f'❌ API request failed: {e}')
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f'❌ Invalid JSON response: {e}')
    sys.exit(1)
