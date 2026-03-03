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
    "factory farming: confinement of pigs in gestation crates",
    "factory farming: debeaking of chickens without anesthesia",
    "poaching: the use of wire snares in forests",
    "poaching: killing rhinos for horns used in medicine",
    "circuses: training elephants using bullhooks (ankush)",
    "circuses: lions living entire lives in small transport cages",
    "animal trade: farming bears for bile extraction",
    "animal trade: pangolins killed for scales in traditional medicine",
    "trophy hunting: killing 'big five' animals for sport and photos",
    "trophy hunting: the impact of 'canned hunting' in fenced areas",
    "laboratory testing: testing cosmetics on rabbits' eyes (Draize test)",
    "live transport: animals traveling for weeks in overcrowded ships",
    "slaughterhouse practices: improper stunning before slaughter",
    "street animal abuse: the harsh reality for dogs and cats",
    "habitat destruction: burning forests for palm oil, killing orangutans",
    "bycatch: dolphins and turtles dying in large-scale fishing nets",
    "foie gras: force-feeding ducks and geese to enlarge their livers",
    "angora wool: plucking fur from live rabbits while they scream",
    "shark finning: cutting off fins and throwing sharks back to drown",
    "mulesing: cutting skin off sheep without anesthesia",
    "silk production: boiling silkworms alive in their cocoons",
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
    """Generates a serious tweet about animal suffering and safety using Gemini."""
    prompt = f"""
    You are 'Matta4Animals', a serious advocate for animal safety and an educator on animal suffering.
    Your mission is to expose the harsh realities that animals face every day so that people will not be oblivious.

    Topic: {topic}

    Instruction:
    1. Write a serious, somber tweet (under 280 characters) that describes a specific, documented occurrence or practice related to the topic.
    2. Focus on the actual suffering or the measure of cruelty involved.
    3. Write the ENTIRE tweet in standard, serious Nigerian Pidgin English. Avoid "fun" or "did you know" excitement. The tone must be blunt and thought-provoking.
    4. Cite the practice or action clearly (e.g., how they treat the animals in that industry).
    5. No quotes, no preamble. 
    6. Include 1-2 relevant hashtags (e.g., #Matta4Animals, #AnimalRights, #StopAnimalCruelty).

    Example Style: "For inside factory farms, dem dey cut chicken mouth (debeaking) without any medicine to dull the pain. Dis na because dem too plenty for small space and dem fit peck each other. Dis suffering too much. #Matta4Animals #StopAnimalCruelty"
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
