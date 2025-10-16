import os
import json
import random
import requests
import re
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
PROFILES_FILE = "profiles.txt"          # One profile URL per line
REPLY_QUEUE_FILE = "reply_queue.json"
RECENT_PROFILES_FILE = "recent_profiles.json"

# ---------------- Settings ----------------
ACTOR_ID = "Fo9GoU5wC270BgcBr"
TWEETS_PER_PROFILE = 1
PROFILES_PER_RUN = 3
RECENT_MEMORY = 10
DRY_RUN = False

# ---------------- Setup Clients ----------------
apify_client = ApifyClient(APIFY_TOKEN)
twitter_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Utils ----------------
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_text(text):
    if not text: return ""
    text = re.sub(r'\[\d+\](?:\[\d+\])*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 273:
        trimmed = text[:273]
        last_stop = max(trimmed.rfind('।'), trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))
        if last_stop > 200: text = trimmed[:last_stop+1]
        else: text = trimmed[:trimmed.rfind(' ')]
        if text[-1] not in {'।', '.', '?', '!'}: text += "..."
    return text.strip()

# ---------------- Profile Selection ----------------
def get_profiles():
    with open(PROFILES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def select_profiles():
    all_profiles = get_profiles()
    recent = load_json(RECENT_PROFILES_FILE).get("recent", [])
    candidates = [p for p in all_profiles if p not in recent]
    if len(candidates) < PROFILES_PER_RUN: candidates = all_profiles
    selected = random.sample(candidates, PROFILES_PER_RUN)
    recent = selected + recent
    recent = recent[:RECENT_MEMORY]
    save_json(RECENT_PROFILES_FILE, {"recent": recent})
    return selected

# ---------------- Apify Fetch ----------------
def fetch_tweets(profiles):
    run_input = {"profileUrls": profiles, "resultsLimit": TWEETS_PER_PROFILE}
    print(f"Fetching {TWEETS_PER_PROFILE} tweet(s) from {len(profiles)} profiles ...")
    run = apify_client.actor(ACTOR_ID).call(run_input=run_input)
    all_tweets = {}
    for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
        profile = item.get("profileUrl")
        if profile not in all_tweets: all_tweets[profile] = []
        if len(all_tweets[profile]) < TWEETS_PER_PROFILE:
            all_tweets[profile].append(item.get("postId"))
    return all_tweets

# ---------------- Perplexity ----------------
def fetch_perplexity_post():
    prompt = ("Respond as a political analyst. Give one recent Hindi tweet criticizing BJP "
              "or its leader based on today's news, max 260 chars.")
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

# ---------------- Twitter ----------------
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
        print(f"✅ Tweeted! ID: {resp.data['id']}")
        return True
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

# ---------------- Main ----------------
def main():
    selected_profiles = select_profiles()
    tweets = fetch_tweets(selected_profiles)

    queue = load_json(REPLY_QUEUE_FILE)

    for i, (profile, tweet_ids) in enumerate(tweets.items()):
        for j, tid in enumerate(tweet_ids):
            if i == 0 and j == 0:
                # Immediately reply to first tweet
                text = fetch_perplexity_post()
                if post_tweet(text, reply_to_id=tid):
                    print(f"✅ Immediately replied to first tweet {tid}")
                else:
                    print(f"⚠️ Failed to reply {tid}")
            else:
                # Add remaining tweets to queue
                if profile not in queue: queue[profile] = []
                if tid not in queue[profile]: queue[profile].append(tid)

    save_json(REPLY_QUEUE_FILE, queue)
    print(f"✅ Queue updated with remaining tweets.")

if __name__ == "__main__":
    main()
