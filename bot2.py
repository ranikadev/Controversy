import os
import requests
from googletrans import Translator
import re
import tweepy
from datetime import datetime, timedelta
import random
import json

# ---------------- Environment Variables ----------------
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.environ.get("TWITTER_ACCESS_SECRET")

# ---------------- Config ----------------
NEWS_FILES = {
    "bjp": "bjp_news.txt",
    "congress": "congress_news.txt",
    "countries": "countries_news.txt",
    "others": "others_news.txt"
}
POSTED_FILE = "posted_news.json"
LAST_FETCH_FILE = "last_fetch.txt"

PROMPTS = {
    "bjp": "give me 9 controversial news each in 200 to 250 characters related to political parties specifically negative for BJP, Today, in hindi",
    "congress": "give me 9 controversial news each in 200 to 250 characters related to political parties specifically negative for congress, Today, in hindi",
    "countries": "give me 5 controversial news each in 200 to 250 characters related to countries, Today, in hindi",
    "others": "give me 9 controversial news each in 200 to 250 characters related to cricket/defence/religion/administration/incident/event, Today, in hindi"
}

# ---------------- Twitter Setup ----------------
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
api = tweepy.API(auth)

translator = Translator()

# ---------------- Utility Functions ----------------
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
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if "answer" in data:
            return data["answer"]
    return ""

def save_news(news_list, filename, replace=True):
    if replace:
        with open(filename, "w", encoding="utf-8") as f:
            for news in news_list:
                f.write(news + "\n")
    else:
        existing = set()
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                existing = set(f.read().splitlines())
        with open(filename, "a", encoding="utf-8") as f:
            for news in news_list:
                if news not in existing:
                    f.write(news + "\n")

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
    posted = {k: v for k, v in posted.items() if datetime.strptime(v, "%Y-%m-%d") >= cutoff}
    save_posted(posted)

def load_news_randomized(today=True):
    files_to_load = {}
    for cat in ["bjp", "congress", "countries", "others"]:
        if os.path.exists(NEWS_FILES[cat]):
            with open(NEWS_FILES[cat], "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if len(line.strip()) >= 150]
                random.shuffle(lines)
                files_to_load[cat] = lines
        else:
            files_to_load[cat] = []

    # Randomize between BJP & Congress
    first_two = files_to_load["bjp"] + files_to_load["congress"]
    random.shuffle(first_two)

    all_news = first_two + files_to_load["countries"] + files_to_load["others"]
    return all_news[:32]

def post_next(today_post=True):
    news_pool = load_news_randomized(today=today_post)
    posted = load_posted()
    for news in news_pool:
        if news not in posted:
            try:
                api.update_status(news)
                print(f"{datetime.now()} - Posted:", news)
                posted[news] = datetime.now().strftime("%Y-%m-%d")
                save_posted(posted)
            except Exception as e:
                print("Error posting:", e)
            break
    else:
        print(f"{datetime.now()} - No new news to post.")

# ---------------- Manual Fetch & Post ----------------
def manual_fetch_post(category):
    category = category.lower()
    if category not in PROMPTS:
        print("Invalid category!")
        return
    print(f"Fetching news for category: {category}")
    raw_news = fetch_news(PROMPTS[category])
    news_list = split_news(raw_news)
    news_list = [to_hindi(n) for n in news_list]
    if not news_list:
        print("No news fetched.")
        return
    save_news(news_list, NEWS_FILES[category], replace=True)
    print(f"Saved {len(news_list)} news in {NEWS_FILES[category]}")
    news_to_post = random.choice(news_list)
    try:
        api.update_status(news_to_post)
        print(f"{datetime.now()} - Posted successfully:", news_to_post)
    except Exception as e:
        print("Error posting:", e)

# ---------------- Main ----------------
if __name__ == "__main__":
    import sys
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    category = sys.argv[2] if len(sys.argv) > 2 else None

    if mode == "manual":
        if not category:
            print("Please provide category for manual mode: bjp/congress/countries/others")
        else:
            manual_fetch_post(category)
    else:
        cleanup_posted(days=5)
        today_str = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().hour

        # Fetch new news at 6 PM
        need_fetch = True
        if os.path.exists(LAST_FETCH_FILE):
            with open(LAST_FETCH_FILE, "r") as f:
                if f.read().strip() == today_str:
                    need_fetch = False

        if current_hour == 18 and need_fetch:
            print(f"{datetime.now()} - Fetching fresh news at 6 PM...")
            for key, prompt in PROMPTS.items():
                raw_news = fetch_news(prompt)
                news_list = split_news(raw_news)
                news_list = [to_hindi(n) for n in news_list]
                save_news(news_list, NEWS_FILES[key], replace=True)
                print(f"Saved {len(news_list)} news in {NEWS_FILES[key]}")
            with open(LAST_FETCH_FILE, "w") as f:
                f.write(today_str)
        else:
            print(f"{datetime.now()} - Fetching skipped. Using existing news.")

        # Post hourly 9 AM → 1 AM
        if 9 <= current_hour <= 23 or 0 <= current_hour <= 1:
            post_next(today_post=(current_hour >= 18))
        else:
            print(f"{datetime.now()} - Outside posting hours. No post.")
