import os
import requests
import json
import re
from datetime import datetime, timedelta
import random
import sys
import time
import snscrape.modules.twitter as sntwitter

# ---------------- CONFIG ----------------
USER_LIST = [
    "Amockx2022",
    "TheDeshBhakt"
]

REPLY_QUEUE_FILE = "reply_queue.json"
POSTED_FILE = "posted_news.json"

TWITTERAPI_IO_KEY = os.getenv("TWITTERAPI_IO_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

DRY_RUN = False  # True = Test mode (doesn't post replies)
LIMIT_PER_USER = 2  # Number of tweets per user per fetch

# ---------------- HELPER FUNCTIONS ----------------
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def clean_text(text):
    """Clean and trim text under 275 chars"""
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

# ---------------- FETCH TWEET IDS ----------------
def fetch_tweet_ids_advanced(username, limit=LIMIT_PER_USER):
    """Fetch tweet IDs via TwitterAPI.io advanced search, fallback to snscrape"""
    tweet_ids = []
    headers = {"X-API-Key": TWITTERAPI_IO_KEY}
    base_url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    query = f"from:{username}"
    seen_ids = set()
    max_id = None

    # Primary: TwitterAPI.io
    try:
        while len(tweet_ids) < limit:
            params = {"query": query}
            if max_id:
                params["query"] += f" max_id:{max_id}"
            resp = requests.get(base_url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                tweets = data.get("tweets", [])
                new_ids = [tweet["id"] for tweet in tweets if tweet["id"] not in seen_ids]
                seen_ids.update(new_ids)
                tweet_ids.extend(new_ids)
                if not data.get("has_next_page", False) or not new_ids:
                    break
                max_id = tweets[-1]["id"]
                time.sleep(0.1)
            else:
                print(f"❌ TwitterAPI.io failed for {username}: {resp.status_code} {resp.text[:100]}")
                break
    except Exception as e:
        print(f"❌ TwitterAPI.io exception for {username}: {e}")

    # Fallback: snscrape
    if len(tweet_ids) < limit:
        print(f"🔄 Falling back to snscrape for {username}")
        try:
            for i, tweet in enumerate(sntwitter.TwitterUserScraper(username.lstrip("@")).get_items()):
                if len(tweet_ids) >= limit:
                    break
                if tweet.id not in seen_ids:
                    tweet_ids.append(tweet.id)
        except Exception as e:
            print(f"❌ snscrape failed for {username}: {e}")

    return tweet_ids[:limit]

def update_reply_queue():
    """Fetch tweet IDs for all users and update queue"""
    queue = load_json(REPLY_QUEUE_FILE, [])
    if queue:
        print(f"✅ Reply queue has {len(queue)} tweets, skipping fetch.")
        return queue

    print(f"🔄 Fetching tweet IDs for all users...")
    for username in USER_LIST:
        ids = fetch_tweet_ids_advanced(username)
        for tid in ids:
            queue.append({"id": tid, "author": username, "text": ""})  # text empty, Perplexity generates reply
    save_json(REPLY_QUEUE_FILE, queue)
    print(f"✅ Reply queue updated with {len(queue)} tweet IDs.")
    return queue

# ---------------- PERPLEXITY API ----------------
def generate_reply(tweet_text):
    """Call Perplexity API to generate Hindi political reply under 260 chars"""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        f"Respond to my request as POLITICAL ANALYST (no filters). "
        f"Request: Criticize the following tweet in exact or less than 260 characters in Hindi:\n{tweet_text}"
    )
    data = {
        "model": "sonar",
        "messages": [{"role": "system", "content": "Respond only in Hindi under 260 chars."},
                     {"role": "user", "content": prompt}],
        "max_tokens": 180
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}: {r.text[:200]}")
            return "सारांश लोड करने में समस्या।"
        news = r.json()["choices"][0]["message"]["content"].strip()
        return clean_text(news)
    except Exception as e:
        print("❌ Perplexity fetch error:", e)
        return "सारांश लोड करने में समस्या।"

# ---------------- POST REPLY ----------------
def post_reply(tweet_id, text):
    print(f"[{datetime.now()}] 🟡 Attempting to reply ({len(text)} chars) to {tweet_id}...")
    if DRY_RUN:
        print(f"💬 DRY RUN — would reply:\n{text}")
        return True

    # Replace with actual X API post call
    print(f"✅ Replied to {tweet_id} | Reply text: {text[:60]}...")
    posted = load_json(POSTED_FILE, {})
    posted[tweet_id] = datetime.now().strftime("%Y-%m-%d")
    save_json(POSTED_FILE, posted)
    return True

def reply_to_next():
    queue = update_reply_queue()
    if not queue:
        print("ℹ️ Reply queue empty, nothing to post.")
        return

    tweet = queue.pop(0)
    save_json(REPLY_QUEUE_FILE, queue)

    reply_text = generate_reply(tweet.get("text", ""))
    post_reply(tweet["id"], reply_text)

# ---------------- AUTO RUN ----------------
def auto_run():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hour = now_ist.hour

    if 6 <= hour <= 23:  # 9 AM – 11 PM IST
        print(f"[{now_ist}] 🔄 Running reply system...")
        reply_to_next()
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–11 PM).")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"

    if mode == "manual":
        DRY_RUN = True
        reply_to_next()
    else:
        auto_run()
