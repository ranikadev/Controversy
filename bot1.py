import os
import requests
import json
import re
from datetime import datetime, timedelta
import random
import sys

# ---------------- CONFIG ----------------
USER_LIST = [
    "@Amockx2022",
    "@TheDeshBhakt"
]

REPLY_QUEUE_FILE = "reply_queue.json"
POSTED_FILE = "posted_news.json"

TWITTERAPI_IO_KEY = os.getenv("TWITTERAPI_IO_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

DRY_RUN = False  # True = Test mode (doesn't post replies)

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

# ---------------- FETCH TWEETS ----------------
def fetch_tweets(limit_per_user=2):
    """Fetch recent tweets from all usernames via TwitterAPI.io"""
    tweets = []
    headers = {"x-api-key": TWITTERAPI_IO_KEY}

    for username in USER_LIST:
        try:
            url = f"https://api.twitterapi.io/user/tweets?username={username}&limit={limit_per_user}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for t in data.get("data", []):
                    if t["id"] not in load_json(POSTED_FILE, {}):
                        tweets.append({"id": t["id"], "author": username, "text": t.get("text", "")})
            else:
                print(f"❌ Error fetching tweets for {username}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"❌ Exception fetching tweets for {username}: {e}")

    return tweets

# ---------------- REPLY QUEUE ----------------
def update_reply_queue():
    queue = load_json(REPLY_QUEUE_FILE, [])
    if queue:
        print(f"✅ Reply queue has {len(queue)} tweets, skipping fetch.")
        return queue

    print(f"🔄 Fetching tweets for all users via TwitterAPI.io...")
    tweets = fetch_tweets()

    if tweets:
        queue.extend(tweets)
        save_json(REPLY_QUEUE_FILE, queue)
        print(f"✅ Reply queue updated with {len(tweets)} tweets.")
    else:
        print("⚠️ No tweets fetched.")

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
    # For example using Tweepy or requests
    print(f"✅ Replied to {tweet_id} | Reply text: {text[:60]}...")
    # Mark as posted
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

    reply_text = generate_reply(tweet["text"])
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
