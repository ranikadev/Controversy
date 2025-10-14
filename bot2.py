import os
import json
import random
import time
from datetime import datetime, timedelta
import requests
import tweepy

# ========== CONFIG ==========
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# ========== FILES ==========
NEWS_FILE = "news_data.json"
POSTED_FILE = "posted_news.json"

# ========== PROMPTS ==========
PROMPTS = {
    "bjp": "give me 9 controversial news each in 200 to 250 cherecters related to political parties specifically negative for BJP, Today, in hindi",
    "congress": "give me 9 controversial news each in 200 to 250 cherecters related to political parties specifically negative for congress, Today, in hindi",
    "countries": "give me 5 controversial news each in 200 to 250 cherecters related to counties , Today , in hindi",
    "others": "give me 9 controversial news each in 200 to 250 cherecters related to cricket/ defence/religion/administration/incident/event, Today , in hindi"
}

# ========== TWITTER AUTH ==========
def twitter_client():
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    )
    return tweepy.API(auth)

# ========== FETCH FROM PERPLEXITY ==========
def fetch_news(category):
    print(f"{datetime.now()} - Fetching news for category: {category}")
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": PROMPTS[category]}]
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error parsing Perplexity response:", e)
        return []

    # Split and clean news
    news_items = [n.strip() for n in text.split("\n") if len(n.strip()) > 150]
    print(f"✅ {len(news_items)} news fetched for {category}")
    return news_items

# ========== LOAD / SAVE ==========
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========== POST TO TWITTER ==========
def post_to_twitter(api, text):
    try:
        api.update_status(text)
        print(f"🟢 Posted: {text[:40]}...")
        return True
    except Exception as e:
        print(f"❌ Failed to post: {e}")
        return False

# ========== CLEANUP ==========
def cleanup_posted(days=5):
    posted = load_json(POSTED_FILE)
    now = datetime.utcnow()
    for date_str in list(posted.keys()):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if (now - dt).days > days:
            del posted[date_str]
    save_json(POSTED_FILE, posted)

# ========== MAIN LOGIC ==========
def main(mode="auto", category=None):
    api = twitter_client()
    cleanup_posted(days=5)

    # Convert to IST
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_minute = now.minute

    news_data = load_json(NEWS_FILE)
    posted = load_json(POSTED_FILE)

    # ---- MANUAL MODE ----
    if mode == "manual" and category:
        print(f"Manual fetch for {category}")
        news_data[category] = fetch_news(category)
        save_json(NEWS_FILE, news_data)
        if news_data[category]:
            news = random.choice(news_data[category])
            if post_to_twitter(api, news):
                posted.setdefault(today_str, []).append(news)
                save_json(POSTED_FILE, posted)
        return

    # ---- AUTO MODE ----
    # Only fetch new news at 6 PM ± 30 min IST
    if 17 <= current_hour <= 18 or (current_hour == 19 and current_minute <= 30):
        if abs((current_hour * 60 + current_minute) - (18 * 60)) <= 30:
            print("🕕 Within 6PM ±30min window — fetching all categories.")
            for cat in PROMPTS.keys():
                news_data[cat] = fetch_news(cat)
            save_json(NEWS_FILE, news_data)
        else:
            print(f"{now} - Outside ±30 min window. Fetch skipped.")
    else:
        print(f"{now} - Outside ±30 min window. Fetch skipped.")

    # Merge all categories (1→2→3→4)
    merged_news = []
    for cat in ["bjp", "congress", "countries", "others"]:
        merged_news.extend(news_data.get(cat, []))

    # Post if available and not already posted
    for news in merged_news:
        if len(news) < 150 or news in sum(posted.values(), []):
            continue
        if post_to_twitter(api, news):
            posted.setdefault(today_str, []).append(news)
            save_json(POSTED_FILE, posted)
            break
    else:
        print(f"{now} - No new news to post.")

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    category = sys.argv[2] if len(sys.argv) > 2 else None
    main(mode, category)
