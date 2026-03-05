import json
import logging
import os
import sys
import time

import schedule
import tweepy
from dotenv import load_dotenv
from google import genai

from modules.rss_fetcher import RSSFeedManager
from modules.story_scorer import StoryScorer
from modules.story_selector import StorySelector
from modules.thread_generator import ThreadGenerator
from modules.twitter_poster import TwitterPoster

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure APIs
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

# Bot Configuration
RSS_FETCH_HOURS = int(os.getenv("RSS_FETCH_HOURS", "48"))
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", "50"))
POST_HISTORY_DAYS = int(os.getenv("POST_HISTORY_DAYS", "30"))
MAX_THREAD_LENGTH = int(os.getenv("MAX_THREAD_LENGTH", "10"))
POST_TIME = os.getenv("POST_TIME", "10:00")

# Configure Gemini
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)


def get_twitter_client():
    """Returns a Tweepy Client for Twitter API v2."""
    if DRY_RUN:
        return None
    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )


def load_config():
    """Load configuration files."""
    # Load RSS feeds
    with open('config/rss_feeds.json', 'r') as f:
        rss_config = json.load(f)

    # Load source scores
    with open('config/source_scores.json', 'r') as f:
        source_config = json.load(f)

    return rss_config, source_config


def daily_job():
    """Main daily job: Fetch RSS, score stories, generate thread, post."""
    logger.info("=" * 60)
    logger.info("Starting daily bot run...")
    logger.info("=" * 60)

    try:
        # Load configuration
        rss_config, source_config = load_config()

        # Phase 1: Fetch RSS stories
        logger.info("\n[PHASE 1] Fetching RSS feeds...")
        rss_manager = RSSFeedManager(
            feed_urls=rss_config['feeds'],
            fetch_hours=RSS_FETCH_HOURS
        )
        stories = rss_manager.fetch_all_feeds()

        if not stories:
            logger.warning("No stories fetched from RSS feeds. Exiting.")
            return

        logger.info(f"✓ Fetched {len(stories)} stories from RSS feeds")

        # Phase 2: Score stories
        logger.info("\n[PHASE 2] Scoring stories with Gemini...")
        scorer = StoryScorer(
            client=gemini_client,
            source_credibility=source_config['source_credibility'],
            story_type_keywords=source_config['story_type_keywords']
        )

        scored_stories = scorer.score_all_stories(stories)

        logger.info(f"✓ Scored {len(scored_stories)} stories")

        # Phase 3: Select best story
        logger.info("\n[PHASE 3] Selecting best story...")
        selector = StorySelector(
            history_file="data/post_history.json",
            history_days=POST_HISTORY_DAYS,
            min_score=MIN_SCORE_THRESHOLD
        )
        best_story = selector.select_best_story(scored_stories)

        if not best_story:
            logger.warning("No story selected. Exiting.")
            return

        if best_story.total_score < MIN_SCORE_THRESHOLD:
            logger.warning(f"⚠ Best story scored {best_story.total_score} (below threshold of {MIN_SCORE_THRESHOLD})")

        logger.info(f"✓ Selected: {best_story.title}")
        logger.info(f"  Score: {best_story.total_score}")
        logger.info(f"  Source: {best_story.source}")
        logger.info(f"  Reasoning: {best_story.reasoning}")

        # Phase 4: Generate thread
        logger.info("\n[PHASE 4] Generating thread with Gemini...")
        thread_gen = ThreadGenerator(
            client=gemini_client,
            max_thread_length=MAX_THREAD_LENGTH
        )
        thread = thread_gen.generate_thread(best_story)

        logger.info(f"✓ Generated {thread.thread_length}-tweet thread")
        logger.info(f"  Hashtags: {', '.join(thread.hashtags)}")
        logger.info(f"  Reasoning: {thread.reasoning_for_length}")

        # Phase 5: Post to Twitter
        logger.info("\n[PHASE 5] Posting to Twitter...")

        if DRY_RUN:
            logger.info("=" * 60)
            logger.info("[DRY RUN MODE] Thread preview:")
            logger.info("=" * 60)
            for i, tweet in enumerate(thread.tweets, 1):
                logger.info(f"\nTweet {i}/{thread.thread_length}:")
                logger.info(f"  {tweet}")
                logger.info(f"  ({len(tweet)} characters)")
            logger.info("\n" + "=" * 60)
            logger.info("[DRY RUN] Thread not actually posted to Twitter")
            logger.info("=" * 60)
        else:
            twitter_client = get_twitter_client()
            poster = TwitterPoster(twitter_client)
            tweet_ids = poster.post_thread(thread)

            logger.info(f"✓ Thread posted successfully!")
            logger.info(f"  Tweet IDs: {tweet_ids}")
            logger.info(f"  First tweet: https://twitter.com/user/status/{tweet_ids[0]}")

            # Add to history
            selector.add_to_history(best_story)
            logger.info("✓ Added to post history")

        logger.info("\n" + "=" * 60)
        logger.info("Daily run completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in daily job: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info(f"Matta4Animals Bot initialized")
    logger.info(f"Post time: {POST_TIME}")
    logger.info(f"Dry Run Mode: {DRY_RUN}")
    logger.info(f"RSS Fetch Hours: {RSS_FETCH_HOURS}")
    logger.info(f"Min Score Threshold: {MIN_SCORE_THRESHOLD}")
    logger.info(f"Max Thread Length: {MAX_THREAD_LENGTH}")

    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        logger.info("\nRunning once as requested by --once argument...")
        daily_job()
        sys.exit(0)

    # Run once immediately for testing if dry run is on
    if DRY_RUN:
        logger.info("\nRunning initial dry run...")
        daily_job()

    # Schedule the job
    schedule.every().day.at(POST_TIME).do(daily_job)

    logger.info(f"\nBot is now running and scheduled for daily posts at {POST_TIME}")
    while True:
        schedule.run_pending()
        time.sleep(60)
