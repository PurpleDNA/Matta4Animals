import logging
import os
import random
import time

import schedule
import tweepy
from dotenv import load_dotenv
from google import genai

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

# Configure Gemini
client = genai.Client(api_key=GOOGLE_API_KEY)
# Topic Pool
TOPICS = [
    "animal protection",
    "animal advocacy",
    "factory farming",
    "alternative proteins",
    "animal policy",
    "AI safety",
    "AI for animals",
    "effective altruism",
    "moral circle expansion",
    "existential risk",
    "longtermism for animals",
    "animal suffering",
    "fun facts about animals",
    "animal cruelty",
    "animal exploitation",
    "poaching",
    "unknown animal practices",
    "marine life protection",
    "wildlife conservation in Nigeria",
    "the intelligence of pigs",
    "how bees communicate",
    "why we should care about insects",
    "the ethics of zoos",
    "pet adoption vs buying",
    "street dogs in Nigeria",
    "animal law",
    "the sentience of fish",
]


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


def generate_content(topic):
    """Generates a tweet about a given topic using Gemini."""
    prompt = f"""
    You are 'Matta4Animals', a passionate Nigerian educator. You share mind-blowing facts about animals, ethics, and the future (including AI).
    Your audience is casual Nigerians on Twitter. Your goal is to make them say "Ah, I no know that one before!"

    Topic: {topic}

    Instruction:
    1. Share a specific, surprising 'Did you know?' fact or a deep insight about the topic.
    2. Write the ENTIRE tweet in standard, relatable Nigerian Pidgin English.
    3. Use a tone that is educational, surprising, and slightly provocative (to spark thought), but not aggressive.
    4. Keep it under 280 characters.
    5. Include 1-2 relevant hashtags (e.g., #Matta4Animals, #AnimalEthics).
    6. No quotes, no preamble like "Here is your tweet".

    Example Style: "You sabi say some fish get memory pass wetin people dey talk? Dem fit remember face for years! Animals get sense o, make we treat dem well. #Matta4Animals"
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return None


def post_tweet():
    """Main job: pick a topic, generate content, and post to Twitter."""
    topic = random.choice(TOPICS)
    logger.info(f"Selected Topic: {topic}")

    content = generate_content(topic)
    if not content:
        logger.warning("Failed to generate content.")
        return

    logger.info(f"Generated Content: {content}")

    if DRY_RUN:
        logger.info("[DRY RUN] Tweet not actually posted.")
    else:
        twitter_client = get_twitter_client()
        try:
            response = twitter_client.create_tweet(text=content)
            logger.info(f"Tweet posted successfully! ID: {response.data['id']}")
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")


def handle_replies():
    """
    Simulation of reply logic.
    NOTE: Reading mentions requires Twitter API Basic tier ($100/mo).
    """
    logger.info("Checking for mentions (simulation)...")
    if DRY_RUN:
        logger.info("[REPLY LOGIC] Skipping check in dry run.")
        return

    # In a real scenario with Basic tier, you would use:
    # client = get_twitter_client()
    # mentions = client.get_users_mentions(id=YOUR_USER_ID)

    logger.info(
        "Mentions reading is restricted on Free Tier. Implement this logic if you upgrade to Basic Tier."
    )


def daily_job():
    logger.info("Starting daily bot run...")
    post_tweet()
    handle_replies()
    logger.info("Daily run completed.")


if __name__ == "__main__":
    import sys
    
    post_time = os.getenv("POST_TIME", "10:00")
    logger.info(f"Twitter Bot initialized. Post time: {post_time}")
    logger.info(f"Dry Run Mode: {DRY_RUN}")

    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        logger.info("Running once as requested by --once argument...")
        daily_job()
        sys.exit(0)

    # Run once immediately for testing if dry run is on
    if DRY_RUN:
        logger.info("Running initial dry run...")
        daily_job()

    # Schedule the job
    schedule.every().day.at(post_time).do(daily_job)

    logger.info("Bot is now running and scheduled.")
    while True:
        schedule.run_pending()
        time.sleep(60)
