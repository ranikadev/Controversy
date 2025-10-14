import os
import requests
import tweepy
from googletrans import Translator
import re
import json
import random
from datetime import datetime, timedelta

# ---------------- Environment Variables ----------------
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# ---------------- File Paths ----------------
NEWS_FILES = {
    "bjp": "bjp_news.txt",
    "congress": "congress_news.txt",
    "countries": "countries_news.txt",
    "others": "others_news.txt"
}
POSTED_FILE = "posted_news.json"
LAST_FETCH_FILE = "last_fetch.txt"

# ---------------- Prompts ----------------
PROMPTS = {
    "bjp": "give me 9 controversial news each in 200 to 250 characters related to political parties specifically negative for BJP, Today, in hindi",
    "congress": "give me 9 controversial news each in 200 to 250 characters related to political parties specifically negative for congress, Today, in hindi",
    "countries": "give me 5 controversial news each in 200 to 250 characters related to countries, Today, in hindi",
    "others": "give me 9 controversial news each in 200 to 250 characters related to cricket/defence/religion/administration/incident/event, Today, in hindi"
}

# ---------------- Twitter Setup (v2 API) ----------------
client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

translator = Translator()

# ---------------- Helper Functions ----------------
def is_hindi(text):
    return any('\u0900' <= ch <= '\u097F' for ch in text)

def to_hindi(text):
    if not is_hindi(text):
        try:
            return translator.translate(text, dest='hi').text
        except:
            return text
    return text

def split_news(raw_news):
    raw_news = raw_news.strip()
    items = re.split(r'\d+\.\s', raw_news)
    items = [i.strip() for i in items if i.strip()]
    if len(items) < 2:
        items = [s.strip() for s in re.split(r'\n|(?<=\.)\s', raw_news) if 200 <= len(s.strip()) <= 250]
    return [i for i in items if 200 <= len(i) <= 250]

def fetch_news(prompt):
    url = "https://api.perplexity.ai/sonar"
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    payload = {"query": prompt}
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        return data.get("answer", "")
    except Exception as e:
        print("❌ Fetch error:", e)
        return ""

def save_news(news_list, filename):
    with open(filename, "w", encoding="utf-8") as f:
        for n in news_list:
            f.write(n + "\n")

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

def cleanup_posted(days=5):
    posted = load_posted()
    cutoff = datetime.now() - timedelta(days=days)
    new_posted = {k: v for k, v in posted.items() if datetime.strptime(v, "%Y-%m-%d") >= cutoff}
    save_posted(new_posted)

def load_all_news():
    all_news = []
    for cat, file in NEWS_FILES.items():
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if len(l.strip()) >= 150]
                all_news.extend(lines)
    random.shuffle(all_news)
    return all_news[:32]

def post_tweet(text):
    try:
        client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Posted: {text[:70]}...")
        return True
    except Exception as e:
        print(f"❌ Tweet failed: {e}")
        return False

def post_next():
    news_list = load_all_news()
    posted = load_posted()

    for news in news_list:
        if news not in posted:
            if post_tweet(news):
                posted[news] = datetime.now().strftime("%Y-%m-%d")
                save_posted(posted)
            return
    print(f"[{datetime.now()}] ℹ️ No new news to post.")

# ---------------- Manual Fetch ----------------
def manual_fetch_post(category):
    category = category.lower()
    if category not in PROMPTS:
        print("⚠️ Invalid category.")
        return

    print(f"[{datetime.now()}] 🟡 Manual fetch for '{category}'")
    raw_news = fetch_news(PROMPTS[category])
    news_list = [to_hindi(n) for n in split_news(raw_news)]
    if not news_list:
        print(f"⚠️ No valid news fetched for {category}.")
        return

    save_news(news_list, NEWS_FILES[category])
    print(f"✅ Saved {len(news_list)} news for {category}")
    chosen = random.choice(news_list)
    post_tweet(chosen)

# ---------------- Main Scheduler ----------------
if __name__ == "__main__":
    import sys

    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    category = sys.argv[2] if len(sys.argv) > 2 else None

    cleanup_posted(days=5)

    if mode == "manual":
        if not category:
            print("Usage: python bot2.py manual [bjp|congress|countries|others]")
        else:
            # ONLY run manual fetch/post, skip all auto logic
            manual_fetch_post(category)
        # exit here to prevent auto-fetch or auto-post
        sys.exit()

    # ---------------- AUTO MODE ----------------
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hour = now.hour
    minute = now.minute

    # Auto fetch at 6 PM ±30 min
    need_fetch = True
    if os.path.exists(LAST_FETCH_FILE):
        with open(LAST_FETCH_FILE) as f:
            if f.read().strip() == today:
                need_fetch = False

    if (17 <= hour <= 18) and need_fetch:
        if (hour == 17 and minute >= 30) or (hour == 18 and minute <= 30):
            print(f"[{now}] 🔄 Fetching fresh news within ±30 min of 6 PM...")
            for key, prompt in PROMPTS.items():
                raw_news = fetch_news(prompt)
                news_list = [to_hindi(n) for n in split_news(raw_news)]
                save_news(news_list, NEWS_FILES[key])
                print(f"✅ Saved {len(news_list)} news for {key}")
            with open(LAST_FETCH_FILE, "w") as f:
                f.write(today)
        else:
            print(f"[{now}] ⏰ Outside ±30 min window — fetch skipped.")
    else:
        print(f"[{now}] ⏰ Fetch skipped (already done or not in window).")

    # Post hourly between 9 AM – 1 AM
    if 9 <= hour <= 23 or 0 <= hour <= 1:
        post_next()
    else:
        print(f"[{now}] 💤 Outside posting hours (9 AM–1 AM). No post.")
