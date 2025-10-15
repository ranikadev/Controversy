import os
import requests
import tweepy
import re
import json
import random
from datetime import datetime, timedelta
import sys

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
FETCH_INDEX_FILE = "fetch_index.txt"
LAST_CYCLE_DAY_FILE = "last_cycle_day.txt"

# ---------------- Prompts ----------------

PROMPTS = {
    "bjp": "Give one critical political controversy for today related to BJP in exactly 260 characters, in Hindi.",
    "congress": "Give one critical political controversy for today related to Congress in exactly 260 characters, in Hindi.",
    "countries": "Give one critical political controversy for today related to countries in exactly 260 characters, in Hindi.",
    "others": "Give one critical political controversy for today related to religious context in exactly 260 characters, in Hindi."
}

# ---------------- Twitter Setup (v2 API) ----------------

client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Global Flag for Dry Run ----------------

DRY_RUN = False  # Set to True for manual mode (no actual tweeting)

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
            {"role": "system", "content": "Respond only with one news item in Hindi, exactly 260 characters."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180  # Limit to ~260 chars
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
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
    Clean a single Hindi news item, handling concatenated or repeated text.
    Removes citations like [1], [17][9] and extra formatting.
    Targets ~260 chars but ensures always <275 chars.
    Returns a list with one valid item (>=20 chars) or empty list.
    """
    if not raw_news:
        return []

    # Strip whitespace
    raw_news = raw_news.strip()

    # Remove citations like [1], [17][9]
    raw_news = re.sub(r'\[\d+\](?:\[\d+\])*', '', raw_news)

    # Normalize whitespace
    raw_news = re.sub(r'\s+', ' ', raw_news).strip()

    # Ensure length <275 and target ~260 by trimming if necessary
    if len(raw_news) > 260:
        # Trim to last word boundary before 260 chars
        trimmed = raw_news[:260].strip()
        last_space = trimmed.rfind(' ')
        if last_space > 200:
            raw_news = trimmed[:last_space].strip()
        else:
            raw_news = trimmed

    # Treat as single item
    news_list = []
    if len(raw_news) >= 20:
        news_list.append(raw_news)

    # Deduplicate and return
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
    global DRY_RUN
    # Verify env vars (one-time check if not dry run)
    if not DRY_RUN and (TWITTER_API_KEY is None or TWITTER_API_SECRET is None or TWITTER_ACCESS_TOKEN is None or TWITTER_ACCESS_SECRET is None):
        print("❌ CRITICAL: Twitter env vars missing! Check .env or export:")
        print(f"  TWITTER_API_KEY: {'SET' if TWITTER_API_KEY else 'MISSING'}")
        print(f"  TWITTER_API_SECRET: {'SET' if TWITTER_API_SECRET else 'MISSING'}")
        print(f"  TWITTER_ACCESS_TOKEN: {'SET' if TWITTER_ACCESS_TOKEN else 'MISSING'}")
        print(f"  TWITTER_ACCESS_SECRET: {'SET' if TWITTER_ACCESS_SECRET else 'MISSING'}")
        return False

    print(f"[{datetime.now()}] 🔄 Attempting to post ({len(text)} chars): {text[:50]}...")
    if DRY_RUN:
        print(f"[{datetime.now()}] ℹ️ DRY RUN: Would post tweet - '{text[:100]}...' (no API call)")
        return True  # Simulate success for dry run

    try:
        response = client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Posted successfully! Tweet ID: {response.data['id']}")
        return True
    except tweepy.TweepyException as e:
        print(f"❌ Tweepy error: Type={type(e).__name__}, Message={str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"  HTTP Status: {e.response.status_code}")
            print(f"  Response: {e.response.text[:200]}...")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: Type={type(e).__name__}, Message={str(e)}")
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
    global DRY_RUN
    DRY_RUN = True  # Enable dry run for manual mode

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

    print(f"📜 Raw news ({len(raw_news)} chars): {raw_news}")

    news_list = split_news(raw_news)  

    if not news_list:  
        print(f"⚠️ No valid news items for {category}, posting default message.")  
        post_tweet("Good day")  
        return  

    print(f"📄 Split/processed news ({len(news_list[0])} chars): {news_list[0]}")

    save_news(news_list, NEWS_FILES[category])  
    print(f"✅ Saved {len(news_list)} news for {category}")  

    chosen = random.choice(news_list)  
    print(f"🎯 Selected to post: {chosen[:50]}... ({len(chosen)} chars)")
    post_tweet(chosen)

# ---------------- Main Scheduler ----------------

if __name__ == "__main__":
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

    categories = list(PROMPTS.keys())

    # Post hourly between 9 AM – 1 AM IST  
    if 9 <= hour <= 23 or 0 <= hour <= 1:  
        # Fetch next category in cycle
        if os.path.exists(LAST_CYCLE_DAY_FILE):
            with open(LAST_CYCLE_DAY_FILE) as f:
                last_day = f.read().strip()
        else:
            last_day = None

        if last_day != today:
            idx = 0
            with open(LAST_CYCLE_DAY_FILE, "w") as f:
                f.write(today)
        else:
            if os.path.exists(FETCH_INDEX_FILE):
                with open(FETCH_INDEX_FILE) as f:
                    idx = int(f.read().strip())
            else:
                idx = 0

        cat = categories[idx]
        print(f"[{now_ist}] 🔄 Fetching fresh news for '{cat}'...")  

        raw_news = fetch_news(PROMPTS[cat])  
        print(f"\n📜 Raw news for {cat}:\n{raw_news[:1000]}\n{'-'*50}")  
        if not raw_news:  
            print(f"⚠️ API returned empty news for {cat}")  
        else:  
            news_list = split_news(raw_news)  

            if news_list:  
                save_news(news_list, NEWS_FILES[cat])  
                print(f"✅ Saved {len(news_list)} news for {cat}")  
            else:  
                print(f"⚠️ No valid news items after splitting for {cat}")  

        # Update index for next cycle
        idx = (idx + 1) % len(categories)
        with open(FETCH_INDEX_FILE, "w") as f:
            f.write(str(idx))

        post_next()  
    else:  
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–1 AM IST). No post.")
