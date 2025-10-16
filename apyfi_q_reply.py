import os
import json
import re
import requests
import tweepy

# ---------------- Config ----------------
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

REPLY_QUEUE_FILE = "reply_queue.json"
DRY_RUN = False

# ---------------- Twitter Client ----------------
twitter_client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)

# ---------------- Utils ----------------
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def clean_text(text):
    if not text: return ""
    text = re.sub(r'\[\d+\](?:\[\d+\])*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 273:
        trimmed = text[:273]
        last_stop = max(trimmed.rfind('।'), trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))
        if last_stop > 200: text = trimmed[:last_stop+1]
        else: text = trimmed[:trimmed.rfind(' ')]
        if text[-1] not in {'।', '.', '?', '!'}: text += "..."
    return text.strip()

# ---------------- Perplexity ----------------
def fetch_perplexity_post():
    prompt = ("Respond as a political analyst. Give one recent Hindi tweet criticizing BJP "
              "or its leader based on today's news, max 260 chars.")
    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Respond with one Hindi news tweet under 260 chars."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 180
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        if r.status_code != 200:
            print(f"❌ Perplexity API error {r.status_code}")
            return ""
        return clean_text(r.json()["choices"][0]["message"]["content"].strip())
    except Exception as e:
        print("❌ Perplexity fetch error:", e)
        return ""

# ---------------- Twitter ----------------
def post_tweet(text, reply_to_id=None):
    if not text:
        print("⚠️ Empty text, skipping.")
        return False
    try:
        if DRY_RUN:
            print(f"💬 DRY RUN: {text}")
            return True
        if reply_to_id:
            resp = twitter_client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id)
        else:
            resp = twitter_client.create_tweet(text=text)
        print(f"✅ Tweeted! ID: {resp.data['id']}")
        return True
    except Exception as e:
        print(f"❌ Post error: {e}")
        return False

# ---------------- Main ----------------
def main():
    queue = load_json(REPLY_QUEUE_FILE)
    if not queue:
        print("⚠️ Queue empty, nothing to reply.")
        return

    # Get first tweet from the queue
    for profile in list(queue.keys()):
        if queue[profile]:
            tweet_id = queue[profile].pop(0)
            text = fetch_perplexity_post()
            if post_tweet(text, reply_to_id=tweet_id):
                print(f"✅ Replied to tweet {tweet_id} from {profile}")
            else:
                print(f"⚠️ Failed to reply {tweet_id}")
            if not queue[profile]:
                del queue[profile]
            save_json(REPLY_QUEUE_FILE, queue)
            break  # Only one reply per run

if __name__ == "__main__":
    main()
