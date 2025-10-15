import os
import requests
import tweepy
import re
import json
import random
from datetime import datetime, timedelta
import sys
from collections import Counter
import time
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    print("⚠️ python-dotenv not installed. Run 'pip install python-dotenv' or set env vars manually.")
    sys.exit(1)

# Load environment variables from .env
load_dotenv()

# ---------------- Environment Variables ----------------

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

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

# ---------------- Real X Trending Keyword Fetch ----------------

def get_trending_keyword_from_x(category, date_str=None):
    """
    Fetch one trending keyword from X (Twitter) using real API search with Bearer Token.
    Returns a single keyword or empty string on failure.
    """
    if date_str is None:
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        date_str = now_ist.strftime("%Y-%m-%d")

    if not TWITTER_BEARER_TOKEN:
        print("⚠️ TWITTER_BEARER_TOKEN missing. Check .env or X Developer Portal.")
        return ""

    # Query map for X search
    query_map = {
        "bjp": f"BJP politics India since:{date_str}",
        "congress": f"Congress politics India since:{date_str}",
        "countries": f"international politics countries since:{date_str}",
        "others": f"religious controversy India since:{date_str}"
    }
    query = query_map.get(category.lower(), f"politics India since:{date_str}")

    # Separate client for search with Bearer Token
    search_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

    for attempt in range(3):
        try:
            # Real X API search (top 10 recent posts)
            tweets = search_client.search_recent_tweets(
                query=query,
                max_results=10,  # Fixed: 10 is minimum allowed
                tweet_fields=['public_metrics', 'created_at'],
                sort_order='relevancy'
            )
            if tweets.data:
                contents = [tweet.text.lower() for tweet in tweets.data]
                all_text = ' '.join(contents)
                words = re.findall(r'\b\w+\b', all_text)  # Handles Hindi/English
                
                # Stop words (English + Hindi)
                stop_words = {
                    'the', 'and', 'in', 'to', 'of', 'a', 'is', 'for', 'on', 'with', 'by', 'as', 'at', 'be', 'this', 'that', 'it', 'from',
                    'में', 'के', 'से', 'का', 'की', 'है', 'को', 'पर', 'ने', 'भी'
                }
                filtered_words = [w for w in words if w not in stop_words and len(w) >= 4]
                
                if filtered_words:
                    common = Counter(filtered_words).most_common(1)
                    keyword = common[0][0] if common else ""
                    print(f"🔍 X Trending Keyword for {category}: '{keyword}' (from top posts: {[t.text[:50] for t in tweets.data]})")
                    return keyword if len(keyword) <= 20 else ""
                else:
                    print(f"⚠️ No valid keywords found for query: {query}")
                    return ""
            else:
                print(f"⚠️ No tweets found for query: {query}")
                return ""
        except tweepy.TweepyException as e:
            status = getattr(e.response, 'status_code', 'Unknown')
            print(f"⚠️ X API error (attempt {attempt+1}): Status={status}, Message={str(e)}")
            if hasattr(e.response, 'text'):
                print(f"  Response: {e.response.text[:200]}...")
            if status == 429:  # Rate limit
                print(f"  Rate limit headers: {getattr(e.response, 'headers', {})}")
                if attempt < 2:
                    time.sleep(15 * (2 ** attempt))  # Exponential backoff: 15s, 30s
                else:
                    return ""
            else:
                return ""  # Exit on non-429 errors (e.g., 400, 401)
        except Exception as e:
            print(f"⚠️ X keyword fetch error (attempt {attempt+1}): {e}")
            return ""

def generate_prompt(category, date_str=None):
    """
    Generate a dynamic prompt with X trending keyword for the given category and date.
    """
    if date_str is None:
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        date_str = now_ist.strftime("%B %d, %Y")

    keyword = get_trending_keyword_from_x(category, date_str)
    keyword_part = f"involving {keyword} " if keyword else ""

    context_map = {
        "bjp": "political",
        "congress": "political",
        "countries": "international",
        "others": "religious"
    }
    context = context_map.get(category.lower(), "political")

    prompt = f"Give one critical {context} controversy for {date_str} related to {category.capitalize()} {keyword_part}in exactly 260 characters, in Hindi."
    return prompt

# ---------------- Twitter Setup (v2 API for Posting) ----------------

client = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Global Flag for Dry Run ----------------

DRY_RUN = False

# ---------------- Helper Functions ----------------

def fetch_news(category):
    """
    Fetch news from Perplexity using dynamic prompt with X trending keyword.
    """
    prompt = generate_prompt(category)
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
        "max_tokens": 180
    }
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                resp_json = response.json()
                return resp_json["choices"][0]["message"]["content"].strip()
            print(f"❌ API status {response.status_code} (attempt {attempt+1})")
        except Exception as e:
            print(f"❌ Fetch error (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(2)
    return ""

def split_news(raw_news):
    """
    Clean a single Hindi news item, removing citations and trimming to <275 chars.
    """
    if not raw_news:
        return []

    raw_news = raw_news.strip()
    raw_news = re.sub(r'\[\d+\](?:\[\d+\])*', '', raw_news)
    raw_news = re.sub(r'\s+', ' ', raw_news).strip()

    if len(raw_news) > 260:
        trimmed = raw_news[:260].strip()
        last_sentence = max(
            trimmed.rfind('।'), trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'), -1
        )
        if last_sentence > 200:
            raw_news = trimmed[:last_sentence + 1].strip()
        else:
            last_space = trimmed.rfind(' ')
            if last_space > 200:
                raw_news = trimmed[:last_space].strip()
            else:
                raw_news = trimmed
        sentence_enders = {'।', '.', '?', '!'}
        if raw_news and raw_news[-1] not in sentence_enders:
            raw_news += "..."

    news_list = []
    if len(raw_news) >= 20:
        news_list.append(raw_news)

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
        return True

    try:
        response = client.create_tweet(text=text)
        print(f"[{datetime.now()}] ✅ Posted successfully! Tweet ID: {response.data['id']}")
        return True
    except tweepy.TweepyException as e:
        print(f"❌ Tweepy error: Status={getattr(e.response, 'status_code', 'Unknown')}, Message={str(e)}")
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

    fallback_news = random.choice(news_list)
    print(f"[{datetime.now()}] ℹ️ All news already posted. Posting random news again.")
    post_tweet(fallback_news)

def manual_fetch_post(category=None):
    global DRY_RUN
    DRY_RUN = True

    if not category:
        category = "bjp"

    category = category.lower()
    valid_categories = list(NEWS_FILES.keys())
    if category not in valid_categories:
        print(f"⚠️ Invalid category. Choose from: {', '.join(valid_categories)}")
        return

    print(f"[{datetime.now()}] 🟡 Manual fetch for '{category}'")

    prompt = generate_prompt(category)
    print(f"📝 Dynamic prompt with X keyword: {prompt}")

    raw_news = fetch_news(category)
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

    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    hour = now_ist.hour
    minute = now_ist.minute
    today = now_ist.strftime("%Y-%m-%d")

    valid_categories = list(NEWS_FILES.keys())

    if 9 <= hour <= 23 or 0 <= hour <= 1:
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

        cat = valid_categories[idx]
        print(f"[{now_ist}] 🔄 Fetching fresh news for '{cat}'...")

        prompt = generate_prompt(cat)
        print(f"📝 Dynamic prompt with X keyword: {prompt}")

        raw_news = fetch_news(cat)
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

        idx = (idx + 1) % len(valid_categories)
        with open(FETCH_INDEX_FILE, "w") as f:
            f.write(str(idx))

        post_next()
    else:
        print(f"[{now_ist}] 💤 Outside posting hours (9 AM–1 AM IST). No post.")
