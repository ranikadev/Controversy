import os
import json
from apify_client import ApifyClient

# --- Setup ---
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
client = ApifyClient(APIFY_TOKEN)
ACTOR_ID = "Fo9GoU5wC270BgcBr"
PROFILES_FILE = "profiles.txt"
LAST_INDEX_FILE = "last_index.txt"

# --- Get Next Profile ---
def get_next_profile():
    with open(PROFILES_FILE, "r") as f:
        profiles = [line.strip() for line in f if line.strip()]

    if not os.path.exists(LAST_INDEX_FILE):
        idx = 0
    else:
        with open(LAST_INDEX_FILE, "r") as f:
            idx = int(f.read().strip() or 0)

    profile = profiles[idx % len(profiles)]
    next_idx = (idx + 1) % len(profiles)

    with open(LAST_INDEX_FILE, "w") as f:
        f.write(str(next_idx))

    return profile

# --- Fetch latest tweet ---
def fetch_latest_tweet(profile_url):
    run_input = {
        "profileUrls": [profile_url],
        "resultsLimit": 1
    }

    print(f"Fetching latest tweet from {profile_url} ...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        tweet_id = item.get("postId")
        tweet_text = item.get("postText")
        print(f"✅ Latest Tweet: {tweet_id} | {tweet_text}")
        return {"tweet_id": tweet_id, "tweet_text": tweet_text}

    print("❌ No tweet found.")
    return None

# --- Main ---
if __name__ == "__main__":
    profile_url = get_next_profile()
    result = fetch_latest_tweet(profile_url)
    if result:
        with open("latest_tweet.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
