import os
import json
import random
import requests
import re
import time
from datetime import datetime, timedelta
from apify_client import ApifyClient
import tweepy

# ---------------- Config ----------------
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# ---------------- Files ----------------
PROFILES_FILE = "profiles.txt"          # List of profile URLs, one per line
REPLY_QUEUE_FILE = "reply_queue.json"
RECENT_PROFILES_FILE = "recent_profiles.json"

# ---------------- Settings ----------------
ACTOR_ID = "Fo9GoU5wC270BgcBr"  # Apify Twitter Scraper
TWEETS_PER_PROFILE = 1
PROFILES_PER_RUN = 3
RECENT_MEMORY = 10               # Keep track of recent profiles to avoid repetition
DRY_RUN = False                  # True = test mode
DELAY_BETWEEN_REPLIES = 20 * 60  # 20 minutes

# ---------------- Setup Clients ----------------
apify_client = ApifyClient(APIFY_TOKEN)
twitter_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Utility Functions ----------------
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\[\d+\](?:\[\d+\])*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 273:
        trimmed = text[:273]
        last_stop = max(trimmed.rfind('।'), trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))
        if last_stop > 200:
            text = trimmed[:last_stop+1]
        else:
            text = trimmed[:trimmed.rfind(' ')]
        if text[-1] not in {'।', '.', '?', '!'}:
            text += "..."
    return text.strip()

# ---------------- Profile Selection ----------------
def get_profiles():
    with open(PROFILES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def select_profiles():
    all_profiles = get_profiles()
    recent = load_json(RECENT_PROFILES_FILE).get("recent", [])
    candidates = [p for p in all_profiles if p not in recent]
    if len(candidates) < PROFILES_PER_RUN:
        candidates = all_profiles
    selected = random.sample(candidates, PROFILES_PER_RUN)
    recent = selected + recent
    recent = recent[:RECENT_MEMORY]
    save_json(RECENT_PROFILES_FILE, {"recent": recent})
    return selected

# ---------------- Apify Tweet Fetch ----------------
def fetch_tweets(profiles):
    run_input = {
        "profileUrls": profiles,
        "resultsLimit": TWEETS_PER_PROFILE
    }
    print(f"Fetching {TWEETS_PER_PROFILE} tweet(s) from {len(profiles)} profiles ...")
    run = apify_client.actor(ACTOR_ID).call(run_input=run_input)

    all_tweets = {}
    for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
        profile = item.get("profileUrl")
        if profile not in all_tweets:
            all_tweets[profile] = []
        if len(all_tweets[profile]) < TWEETS_PER_PROFILE:
            all_tweets[profile].append(item.get("postId"))
    return all_tweets

def update_queue():
    selected_profiles = select_profiles()
    fetched = fetch_tweets(selected_profiles)

    queue = load_json(REPLY_QUEUE_FILE)

    for profile, tweet_ids in fetched.items():
        if profile not in queue:
            queue[profile] = []
        for tid in tweet_ids:
            if tid not in queue[profile]:
                queue[profile].append(tid)

    save_json(REPLY_QUEUE_FILE, queue)
    total = sum(len(v) for v in queue.values())
    print(f"✅ Queue updated with {total} tweet(s) from {len(selected_profiles)} profiles.")
    return queue

# ---------------- Perplexity API ----------------
def fetch_perplexity_post():
    prompt = (
        "Respond as a political analyst. Give one recent Hindi tweet criticizing BJP or its leader "
        "based on today's news, max 260 characters."
    )
    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond with one Hindi news tweet under 260 chars."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}")
            return ""
        return clean_text(r.json()["choices"][0]["message"]["content"].strip())
    except Exception as e:
        print("❌ Perplexity fetch error:", e)
        return ""

# ---------------- Twitter Post ----------------
def post_tweet(text, reply_to_id=None):
    if not text:
        print("⚠️ Empty text, skipping.")
        return False
    try:
        if DRY_RUN:
            print(f"💬 DRY RUN: {text}")
            return True
        if reply_to_id:
            resp = twitter_client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id)
        else:
            resp = twitter_client.create_tweet(text=text)
        print(f"✅ Replied! Tweet ID: {resp.data['id']}")
        return True
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

# ---------------- Reply Logic ----------------
def reply_all_from_queue():
    queue = load_json(REPLY_QUEUE_FILE)
    if not queue:
        print("ℹ️ Queue empty, updating...")
        queue = update_queue()
        if not queue:
            print("⚠️ No tweets to reply to.")
            return

    tweet_list = []
    for tweet_ids in queue.values():
        tweet_list.extend(tweet_ids)

    for i, tweet_id in enumerate(tweet_list):
        text = fetch_perplexity_post()
        if post_tweet(text, reply_to_id=tweet_id):
            print(f"✅ Replied to tweet {tweet_id}")
        else:
            print(f"⚠️ Failed to reply to tweet {tweet_id}")

        # Remove replied tweet from queue
        for profile in list(queue.keys()):
            if tweet_id in queue[profile]:
                queue[profile].remove(tweet_id)
                if not queue[profile]:
                    del queue[profile]
                break
        save_json(REPLY_QUEUE_FILE, queue)

        # Wait 20 min between replies except last
        if i < len(tweet_list) - 1:
            print("⏱ Waiting 20 minutes before next reply...")
            time.sleep(DELAY_BETWEEN_REPLIES)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print(f"[{datetime.utcnow()} UTC] Starting fetch & reply run...")
    update_queue()
    reply_all_from_queue()
    print(f"[{datetime.utcnow()} UTC] Run complete.")
