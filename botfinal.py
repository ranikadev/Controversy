import os
import requests
import tweepy
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
    "bjp": "give me 4 controversial news each in 200 to 250 characters related to bjp party, Today, in hindi",
    "congress": "give me 1 controversial news each in 200 to 250 characters related to Congress party, Today, in hindi",
    "countries": "give me 1 controversial news each in 200 to 250 characters related to countries, Today, in hindi",
    "others": "give me 4 controversial news each in 200 to 250 characters related to cricket/religion/administration/incident/event, Today, in hindi"
}

# ---------------- Twitter Setup (v2 API) ----------------
client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Helper Functions ----------------
def fetch_news(prompt):
    """
    Fetch news from Perplexity using chat completions endpoint.
    Returns combined news as a single string.
    """
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond only with news in Hindi under 250 characters each."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=2000)
        if response.status_code != 200:
            print(f"❌ API returned status {response.status_code}")
            return ""
        resp_json = response.json()
        news_text = resp_json["choices"][0]["message"]["content"]
        return news_text.strip()
    except Exception as e:
        print("❌ Fetch error:", e)
        return ""

def split_news(raw_news):
    """
    Split numbered raw news into clean Hindi news items.
    Removes trailing citations like [1], [17][9].
    Keeps all news items of length >=20 characters.
    """
    if not raw_news:
        return []

    raw_news = raw_news.strip()
    # Replace numbering like 1. 2. 3. with newline
    raw_news = re.sub(r"\d+[\.\)]\s+", "\n", raw_news)
    # Split by newlines
    items = [i.strip() for i in raw_news.split("\n") if i.strip()]

    news_list = []
    for i in items:
        # Remove trailing [numbers] like [1], [17][9]
        i = re.sub(r'\d+(?:\d+)*', '', i)
        i = re.sub(r'\s+', ' ', i)
        if len(i) >= 20:
            news_list.append(i)

    # Deduplicate
    return list(dict.fromkeys(news_list))

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
                lines = [l.strip() for l in f if len(l.strip()) >= 20]
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
    """
    Posts the next news item from all categories.
    Ensures no duplicates and at least one post per hour.
    """
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

    # If all news already posted, post a random one
    fallback_news = random.choice(news_list)
    print(f"[{datetime.now()}] ℹ️ All news already posted. Posting random news again.")
    post_tweet(fallback_news)

def manual_fetch_post(category=None):
    if not category:
        category = "bjp"

    category = category.lower()
    if category not in PROMPTS:
        print("⚠️ Invalid category.")
        return

    print(f"[{datetime.now()}] 🟡 Manual fetch for '{category}'")
    
    raw_news = fetch_news(PROMPTS[category])
    if not raw_news:
        print(f"⚠️ No news returned by API for {category}")
        post_tweet("Good day")
        return

    news_list = split_news(raw_news)

    if not news_list:
        print(f"⚠️ No valid news items for {category}, posting default message.")
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
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    minute = now_ist.minute
    today = now_ist.strftime("%Y-%m-%d")

    need_fetch = True
    if os.path.exists(LAST_FETCH_FILE):
        with open(LAST_FETCH_FILE) as f:
            if f.read().strip() == today:
                need_fetch = False

    if need_fetch and ((hour == 16 and minute >= 40) or (hour == 17 and minute <= 10 )):
        print(f"[{now_ist}] 🔄 Fetching fresh news for all categories...")
        fetched_any = False
        for key, prompt in PROMPTS.items():
            raw_news = fetch_news(prompt)
            print(f"\n📜 Raw news for {key}:\n{raw_news[:1000]}\n{'-'*50}")
            if not raw_news:
                print(f"⚠️ API returned empty news for {key}")
                continue

            news_list = split_news(raw_news)

            if news_list:
                save_news(news_list, NEWS_FILES[key])
                print(f"✅ Saved {len(news_list)} news for {key}")
                fetched_any = True
            else:
                print(f"⚠️ No valid news items after splitting for {key}")

        if not fetched_any:
            print(f"[{now_ist}] ⚠️ All categories empty, will post default message if needed.")

        with open(LAST_FETCH_FILE, "w") as f:
            f.write(today)
    else:
        print(f"[{now_ist}] ⏰ Outside ±50 min window or already fetched — fetch skipped.")

    # Post hourly between 9 AM – 1 AM IST
    if 9 <= hour <= 23 or 0 <= hour <= 1:
        post_next()
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–1 AM IST). No post.")
