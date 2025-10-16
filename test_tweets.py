import os
import requests
import json
import sys

API_KEY = os.getenv('TWITTERAPI_IO_KEY')
USERNAME = os.getenv('USERNAME')

if not API_KEY:
    raise ValueError('Missing TWITTERAPI_IO_KEY')
if not USERNAME:
    raise ValueError('Missing username')

url = f'https://api.twitterapi.io/twitter/user/last_tweets?userName={USERNAME}'
headers = {'X-API-Key': API_KEY}
r = requests.get(url, headers=headers)
data = r.json()
tweet_ids = [t['id'] for t in data.get('tweets', []) if 'id' in t]
print('✅ Tweet IDs:', tweet_ids)
