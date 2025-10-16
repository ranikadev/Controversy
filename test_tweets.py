import os
import requests

# Read your saved key from environment variable
API_KEY = os.getenv("TWITTERAPI_IO_KEY")

if not API_KEY:
    raise ValueError("❌ Environment variable TWITTERAPI_IO_KEY not found!")

# 👉 Change this to any Twitter username you want to check
USERNAME = "narendramodi"

url = f"https://api.twitterapi.io/twitter/user/last_tweets?userName={USERNAME}"
headers = {"X-API-Key": API_KEY}

print(f"🔹 Fetching tweets for user: {USERNAME}...")

response = requests.get(url, headers=headers)
data = response.json()

if response.status_code == 200 and "tweets" in data:
    tweet_ids = [tweet["id"] for tweet in data["tweets"] if "id" in tweet]
    print("✅ Tweet IDs fetched successfully:")
    print(tweet_ids)
else:
    print(f"❌ Error: {response.status_code}")
    print(data)
