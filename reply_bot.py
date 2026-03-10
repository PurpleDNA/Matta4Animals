"""
Reply bot - monitors mentions and replies to them.

Run this as a separate process alongside bot.py:
    python reply_bot.py              # normal mode
    python reply_bot.py --dry-run    # preview replies without posting
"""

import logging
import os
import sys
import time

import tweepy
from dotenv import load_dotenv
from google import genai

from modules.reply_handler import ReplyHandler

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("reply_bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Configuration
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BOT_USER_ID = os.getenv("BOT_USER_ID")  # Your bot's numeric Twitter user ID
POLL_INTERVAL = int(os.getenv("REPLY_POLL_INTERVAL", "90"))  # seconds
MAX_REPLIES_PER_DAY = int(os.getenv("MAX_REPLIES_PER_DAY", "20"))
MAX_REPLIES_PER_USER = int(os.getenv("MAX_REPLIES_PER_USER_PER_DAY", "3"))


def get_twitter_client() -> tweepy.Client:
    """Returns a Tweepy Client for Twitter API v2."""
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
    )


def get_bot_user_id(client: tweepy.Client) -> str:
    """
    Get the bot's user ID. Uses BOT_USER_ID env var if set,
    otherwise calls Twitter API to look it up.
    """
    if BOT_USER_ID:
        return BOT_USER_ID

    logger.info("BOT_USER_ID not set, fetching from Twitter API...")
    me = client.get_me()
    user_id = str(me.data.id)
    logger.info(f"Bot user ID: {user_id} — set BOT_USER_ID={user_id} in .env to skip this call")
    return user_id


def poll_loop(handler: ReplyHandler, dry_run: bool = False):
    """
    Main polling loop. Fetches mentions and processes them every POLL_INTERVAL seconds.

    The flow each cycle:
    1. Call Twitter API for new mentions since last check
    2. For each mention:
       a. Check if we should reply (rate limits, not our own tweet)
       b. Fetch the parent tweet for context
       c. Send context + mention to Gemini to generate reply
       d. Post the reply to the correct tweet
    3. Sleep for POLL_INTERVAL seconds
    4. Repeat
    """
    logger.info(f"Starting poll loop (interval={POLL_INTERVAL}s, dry_run={dry_run})")

    while True:
        try:
            # Fetch new mentions since last check
            mentions = handler.fetch_new_mentions()

            # Process each mention (oldest first so replies are in order)
            for mention in reversed(mentions):
                handler.process_mention(mention, dry_run=dry_run)
                # Small delay between processing mentions to avoid rate limits
                time.sleep(2)

        except Exception as e:
            logger.error(f"Error in poll cycle: {e}", exc_info=True)

        # Wait before next poll
        logger.info(f"Sleeping {POLL_INTERVAL}s until next poll...")
        time.sleep(POLL_INTERVAL)


def main():
    dry_run = "--dry-run" in sys.argv

    logger.info("=" * 60)
    logger.info("Matta4Animals Reply Bot starting...")
    logger.info(f"  Dry Run: {dry_run}")
    logger.info(f"  Poll Interval: {POLL_INTERVAL}s")
    logger.info(f"  Max Replies/Day: {MAX_REPLIES_PER_DAY}")
    logger.info(f"  Max Replies/User/Day: {MAX_REPLIES_PER_USER}")
    logger.info("=" * 60)

    # Initialize clients
    twitter_client = get_twitter_client()
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    bot_user_id = get_bot_user_id(twitter_client)

    # Initialize handler
    handler = ReplyHandler(
        twitter_client=twitter_client,
        gemini_client=gemini_client,
        bot_user_id=bot_user_id,
        max_replies_per_day=MAX_REPLIES_PER_DAY,
        max_replies_per_user_per_day=MAX_REPLIES_PER_USER,
    )

    # Start polling
    poll_loop(handler, dry_run=dry_run)


if __name__ == "__main__":
    main()
