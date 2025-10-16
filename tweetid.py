import os
import requests
import random
from datetime import datetime

# ---------------- ENVIRONMENT VARIABLES ----------------
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")  # your TwitterAPI.io key

# ---------------- USER LIST ----------------
USERNAMES = [
    "dhruv_rathee",
    "TheDeshBhakt",
    "amockx2022",
    "akshaykumar",
    "PMOIndia",
    "imVkohli",
"SrBachchan",
"BeingSalmanKhan",
"akshaykumar",
"iamsrk",
"sachin_rt",
"iHrithik",
"klrahul",
"priyankachopra",
"YUVSTRONG12"
]

# ---------------- FUNCTION: FETCH TWEET IDS ----------------
def fetch_tweet_ids(username, count=1):
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    params = {
        "query": f"from:{username}",
        "max_results": count,
        "tweet_fields": "id,created_at"
    }
    headers = {"X-API-Key": TWITTER_API_KEY}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            print(f"❌ TwitterAPI.io failed for @{username}: {response.status_code}")
            return []

        data = response.json()
        if "data" not in data:
            print(f"⚠️ No data field for @{username}: {data}")
            return []

        tweet_ids = [tweet["id"] for tweet in data["data"]]
        print(f"✅ {username}: fetched {len(tweet_ids)} tweet IDs")
        return tweet_ids

    except Exception as e:
        print(f"❌ Exception fetching @{username}: {e}")
        return []

# ---------------- MAIN ----------------
if __name__ == "__main__":
    all_tweet_ids = {}
    for user in USERNAMES:
        ids = fetch_tweet_ids(user)
        all_tweet_ids[user] = ids
        # random delay to avoid rate limit
        time_delay = random.randint(2, 5)
        print(f"⏳ Waiting {time_delay}s...")
        import time; time.sleep(time_delay)

    print("\nAll Tweet IDs:")
    for user, ids in all_tweet_ids.items():
        print(f"{user}: {ids}")
