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
url = f'https://api.twitterapi.io/twitter/user/info?userName={USERNAME}
headers = {'X-API-Key': API_KEY}

# ... (existing imports and validations up to headers = ...)

try:
    # Determine user ID
    user_id = os.getenv('USER_ID')
    if not user_id:
        # Fetch user ID from username
        info_url = f'https://api.twitterapi.io/twitter/user/info?userName={USERNAME}'
        info_response = requests.get(info_url, headers=headers)
        print(f"User Info Status: {info_response.status_code}")
        print(f"Full User Info Response: {json.dumps(info_response.json(), indent=2)}")
        if info_response.status_code != 200:
            print(f"User Info Error: {info_response.text}")
            sys.exit(1)
        info_data = info_response.json()
        user_id = info_data.get('user', {}).get('id')
        if not user_id:
            raise ValueError('User ID not found')
    else:
        print(f"Using provided User ID: {user_id}")
    
    # API call for tweets using userId
    url = f'https://api.twitterapi.io/twitter/user/last_tweets?userId={user_id}'
    response = requests.get(url, headers=headers)
    print(f"Tweets Status: {response.status_code}")
    print(f"Full Tweets Response: {json.dumps(response.json(), indent=2)}")
    
    response.raise_for_status()
    data = response.json()
    
    # ... (rest unchanged: extract tweet_ids, print results, except blocks)
    
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
