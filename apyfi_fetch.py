import os
from apify_client import ApifyClient

# Get your Apify API token from repository secrets or environment variables
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
USERNAME = os.getenv("TWITTER_USERNAME", "elonmusk")  # default user

if not APIFY_TOKEN:
    raise ValueError("Missing APIFY_API_TOKEN in environment variables")

# Initialize the Apify client
client = ApifyClient(APIFY_TOKEN)

def fetch_latest_tweets(username: str, max_tweets: int = 2):
    run_input = {
        "maxTweetsPerUser": max_tweets,
        "proxy": {"useApifyProxy": True},
        "startUrls": [f"https://x.com/{username}"],
    }

    print(f"Fetching up to {max_tweets} latest tweets from @{username} ...")

    run = client.actor("epctex/twitter-profile-scraper").call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    dataset = client.dataset(dataset_id).list_items()

    tweets = dataset.items
    tweet_ids = [t["id"] for t in tweets]

    print(f"✅ Found {len(tweet_ids)} tweets:")
    for tid in tweet_ids:
        print(tid)

    return tweet_ids


if __name__ == "__main__":
    fetch_latest_tweets(USERNAME, max_tweets=2)
