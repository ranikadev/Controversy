import os
import requests
import json
import re
from datetime import datetime, timedelta
import time
import sys
import random

# ---------------- CONFIG ----------------
USER_LIST = [
    "Amockx2022",
    "TheDeshBhakt",
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

REPLY_QUEUE_FILE = "reply_queue.json"
POSTED_FILE = "posted_news.json"

TWITTERAPI_IO_KEY = os.getenv("TWITTERAPI_IO_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

DRY_RUN = False  # True = test mode (no real posting)
LIMIT_PER_USER = 2  # tweets per user per fetch

# ---------------- UTILITIES ----------------
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
    """Trim text to <=275 characters neatly"""
    if not text:
        return ""
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
    """Fetch only tweet IDs using TwitterAPI.io (v2 search endpoint)"""
    tweet_ids = []
    headers = {
        "x-api-key": f"Bearer {TWITTERAPI_IO_KEY}",
        "Accept": "application/json"
    }
    base_url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    params = {"query": f"from:{username}", "limit": limit}

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            tweets = data.get("tweets", [])
            tweet_ids = [tweet["id"] for tweet in tweets]
            print(f"✅ {username}: fetched {len(tweet_ids)} tweet IDs.")
        else:
            print(f"❌ TwitterAPI.io failed for {username}: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"❌ TwitterAPI.io exception for {username}: {e}")

    return tweet_ids[:limit]

# ---------------- QUEUE HANDLING ----------------
def update_reply_queue():
    """Fetch tweet IDs for all users and update queue"""
    queue = load_json(REPLY_QUEUE_FILE, [])
    if queue:
        print(f"✅ Reply queue already has {len(queue)} items, skipping new fetch.")
        return queue

    print("🔄 Fetching tweet IDs for all users...")
    for username in USER_LIST:
        ids = fetch_tweet_ids_advanced(username)
        for tid in ids:
            queue.append({"id": tid, "author": username, "text": ""})
    save_json(REPLY_QUEUE_FILE, queue)
    print(f"✅ Reply queue updated with {len(queue)} tweet IDs.")
    return queue

# ---------------- PERPLEXITY ----------------
def generate_reply():
    """Generate a generic Hindi political comment using Perplexity"""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = (
        "Write a 260-character Hindi political commentary on a trending issue — "
        "neutral tone but opinionated, as if replying to a tweet."
    )
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond only in Hindi under 260 characters."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}: {r.text[:200]}")
            return "राजनीतिक टिप्पणी तैयार करने में समस्या।"
        text = r.json()["choices"][0]["message"]["content"].strip()
        return clean_text(text)
    except Exception as e:
        print(f"❌ Perplexity fetch error: {e}")
        return "राजनीतिक टिप्पणी तैयार करने में समस्या।"

# ---------------- POST REPLY ----------------
def post_reply(tweet_id, text):
    print(f"[{datetime.now()}] 🟡 Attempting to reply ({len(text)} chars) to tweet {tweet_id}...")
    if DRY_RUN:
        print(f"💬 DRY RUN — would reply:\n{text}")
        return True

    # Replace this with actual X post logic (e.g., Tweepy)
    print(f"✅ Replied to {tweet_id} | Text: {text[:80]}...")
    posted = load_json(POSTED_FILE, {})
    posted[tweet_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json(POSTED_FILE, posted)
    return True

# ---------------- MAIN LOGIC ----------------
def reply_to_next():
    queue = update_reply_queue()
    if not queue:
        print("ℹ️ Queue empty, nothing to post.")
        return

    tweet = queue.pop(0)
    save_json(REPLY_QUEUE_FILE, queue)

    reply_text = generate_reply()
    post_reply(tweet["id"], reply_text)

def auto_run():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    if 6 <= hour <= 23:  # 9 AM – 11 PM IST
        print(f"[{now_ist}] 🔄 Running reply system...")
        reply_to_next()
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–11 PM IST).")

# ---------------- ENTRY POINT ----------------
if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"

    if mode == "manual":
        DRY_RUN = True
        reply_to_next()
    else:
        auto_run()
