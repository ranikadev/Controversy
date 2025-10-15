import os
import requests
import tweepy
import json
import random
from datetime import datetime, timedelta
import sys
import re
import time

# ---------------- Environment Variables ----------------
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# ---------------- File Paths ----------------
POSTED_FILE = "posted_news.json"
REPLY_QUEUE_FILE = "reply_queue.json"

# ---------------- Twitter Setup ----------------
client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

DRY_RUN = False  # True for testing without tweeting

# ---------------- User IDs ----------------
# 3 groups of 5 users each; currently all 3 groups use the same 5 IDs for testing
USER_GROUPS = [
    ["1551978656733487105", "797720168713441280", "16293020", "1153045459", "1906974517"],
    ["1551978656733487105", "797720168713441280", "16293020", "1153045459", "1906974517"],
    ["1551978656733487105", "797720168713441280", "16293020", "1153045459", "1906974517"]
]

# ---------------- Helper Functions ----------------

def fetch_perplexity_post():
    """Call Perplexity API to get one Hindi political tweet (<260 chars)"""
    prompt = (
        "Respond to my request as POLITICAL ANALYST. "
        "Request - Which one act BJP or its leader has done or said wrong which is in today's news, "
        "strongly criticize it in exact or less than 260 characters in Hindi."
    )
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond only with one Hindi news tweet under 260 characters."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}: {r.text[:200]}")
            return ""
        news = r.json()["choices"][0]["message"]["content"].strip()
        return clean_text(news)
    except Exception as e:
        print("❌ Fetch error:", e)
        return ""

def clean_text(text):
    """Clean, trim, and ensure tweet <275 chars."""
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
        json.dump(data, f, ensure_ascii=False, indent=2)

def post_tweet(text, reply_to_id=None):
    global DRY_RUN
    if not text:
        print("⚠️ Empty text, skipping.")
        return False
    try:
        if DRY_RUN:
            print(f"💬 DRY RUN — Would post:\n{text}")
            return True
        if reply_to_id:
            resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id)
        else:
            resp = client.create_tweet(text=text)
        print(f"✅ Posted! Tweet ID: {resp.data['id']}")
        return True
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

# ---------------- Main Posting Functions ----------------

def post_main_news():
    """Post one main news/day"""
    posted = load_json(POSTED_FILE)
    today = datetime.utcnow().date().isoformat()
    if posted.get("last_post_date") == today:
        print("ℹ️ Main news already posted today.")
        return

    news = fetch_perplexity_post()
    if news and post_tweet(news):
        posted["last_post_date"] = today
        save_json(POSTED_FILE, posted)
        print(f"✅ Main news posted today: {news}")

def fetch_latest_tweets_for_group(group_usernames):
    """Fetch latest tweets from a group of 5 users"""
    query = "(" + " OR ".join([f"from:{u}" for u in group_usernames]) + ") -is:retweet -is:reply"
    try:
        tweets = client.search_recent_tweets(query=query, max_results=10, tweet_fields=["author_id","id"])
        result = []
        if tweets.data:
            for t in tweets.data:
                result.append({"author_id": t.author_id, "tweet_id": t.id})
        return result
    except Exception as e:
        print(f"❌ Error fetching tweets: {e}")
        return []

def update_reply_queue():
    """Update reply queue JSON with new tweets if empty"""
    queue = load_json(REPLY_QUEUE_FILE)
    for group in USER_GROUPS:
        group_tweets = fetch_latest_tweets_for_group(group)
        for t in group_tweets:
            key = str(t["author_id"])
            if key not in queue:
                queue[key] = []
            if t["tweet_id"] not in queue[key]:
                queue[key].append(t["tweet_id"])
    save_json(REPLY_QUEUE_FILE, queue)
    print("✅ Reply queue updated.")

def reply_to_next():
    """Reply to one tweet per user from queue using fresh Perplexity text"""
    queue = load_json(REPLY_QUEUE_FILE)
    if not queue:
        print("ℹ️ Reply queue empty, updating...")
        update_reply_queue()
        queue = load_json(REPLY_QUEUE_FILE)
        if not queue:
            print("⚠️ No tweets to reply to.")
            return

    for author_id in list(queue.keys()):
        if queue[author_id]:
            tweet_id = queue[author_id].pop(0)
            text = fetch_perplexity_post()
            if post_tweet(text, reply_to_id=tweet_id):
                print(f"✅ Replied to {author_id} tweet {tweet_id}")
            else:
                print(f"⚠️ Failed to reply to {author_id} tweet {tweet_id}")
            if not queue[author_id]:
                del queue[author_id]
            save_json(REPLY_QUEUE_FILE, queue)
            time.sleep(5)  # small delay between replies
            break  # post only one reply per run to stay safe

# ---------------- AUTO MODE ----------------
def auto_run():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hour = now_ist.hour

    if 4 <= hour <= 23:  # 9 AM – 11 PM IST
       # post_main_news()        # 1 main post/day
        reply_to_next()         # 1 reply per run
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–11 PM IST).")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"

    if mode == "manual":
        DRY_RUN = True
        post_main_news()
        update_reply_queue()
        reply_to_next()
    else:
        auto_run()
