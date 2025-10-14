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
    "bjp": "give me 9 news each in 200 to 250 characters related to india, Today, in hindi",
    "congress": "give me 9 controversial news each in 200 to 250 characters related to countries , Today, in hindi",
    "countries": "give me 5 controversial news each in 200 to 250 characters related to Science and defence, Today, in hindi",
    "others": "give me 9 controversial news each in 200 to 250 characters related to cricket/religion/administration/incident/event, Today, in hindi"
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
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ API returned status {response.status_code}")
            return ""
        try:
            data = response.json()
        except ValueError:
            print("❌ API returned invalid JSON")
            return ""
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
    cutoff = datetime.utcnow() + timedelta(hours=5, minutes=30) - timedelta(days=days)
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

    if not news_list:
        print(f"[{datetime.now()}] ℹ️ News pool empty, posting default message.")
        post_tweet("Good day")
        return

    for news in news_list:
        if news not in posted:
            if post_tweet(news):
                posted[news] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
                save_posted(posted)
            return
    print(f"[{datetime.now()}] ℹ️ No new news to post.")

# ---------------- Manual Fetch ----------------
def manual_fetch_post(category=None):
    if not category:
        category = "bjp"

    category = category.lower()
    if category not in PROMPTS:
        print("⚠️ Invalid category.")
        return

    print(f"[{datetime.now()}] 🟡 Manual fetch for '{category}'")
    raw_news = fetch_news(PROMPTS[category])
    news_list = [to_hindi(n) for n in split_news(raw_news)]

    if not news_list:
        print(f"⚠️ No valid news fetched for {category}, posting default message.")
        post_tweet("Good day")
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
        manual_fetch_post(category)
        sys.exit()

    # ---------------- AUTO MODE ----------------
    # Convert UTC → IST for GitHub runner
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    minute = now_ist.minute
    today = now_ist.strftime("%Y-%m-%d")

    # Auto fetch at 8 PM IST ±50 min (19:10 → 20:50 IST)
    need_fetch = True
    if os.path.exists(LAST_FETCH_FILE):
        with open(LAST_FETCH_FILE) as f:
            if f.read().strip() == today:
                need_fetch = False

    if (21 <= hour <= 10) and need_fetch:
        if (hour == 21 and minute >= 10) or (hour == 22 and minute <= 50):
            print(f"[{now_ist}] 🔄 Fetching fresh news within ±50 min of 8 PM IST...")
            fetched_any = False
            for key, prompt in PROMPTS.items():
                raw_news = fetch_news(prompt)
                news_list = [to_hindi(n) for n in split_news(raw_news)]
                if news_list:
                    save_news(news_list, NEWS_FILES[key])
                    print(f"✅ Saved {len(news_list)} news for {key}")
                    fetched_any = True
            if not fetched_any:
                print(f"[{now_ist}] ⚠️ All categories empty, will post default message if needed.")
            with open(LAST_FETCH_FILE, "w") as f:
                f.write(today)
        else:
            print(f"[{now_ist}] ⏰ Outside ±50 min window — fetch skipped.")
    else:
        print(f"[{now_ist}] ⏰ Fetch skipped (already done or not in window).")

    # Post hourly between 9 AM – 1 AM IST
    if 9 <= hour <= 23 or 0 <= hour <= 1:
        post_next()
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–1 AM IST). No post.")
