"""Reply handler for responding to mentions."""

import json
import logging
import os
from datetime import datetime, timezone

import tweepy
from google import genai

logger = logging.getLogger(__name__)

# Paths
LAST_MENTION_FILE = "data/last_mention_id.json"
REPLY_HISTORY_FILE = "data/reply_history.json"


class ReplyHandler:
    """Monitors mentions and generates replies."""

    def __init__(
        self,
        twitter_client: tweepy.Client,
        gemini_client: genai.Client,
        bot_user_id: str,
        max_replies_per_day: int = 20,
        max_replies_per_user_per_day: int = 3,
    ):
        """
        Initialize ReplyHandler.

        Args:
            twitter_client: Tweepy client for Twitter API v2
            gemini_client: Gemini client for generating replies
            bot_user_id: The bot's own Twitter user ID (numeric string)
            max_replies_per_day: Max total replies per day
            max_replies_per_user_per_day: Max replies to same user per day
        """
        self.twitter = twitter_client
        self.gemini = gemini_client
        self.bot_user_id = bot_user_id
        self.max_replies_per_day = max_replies_per_day
        self.max_replies_per_user_per_day = max_replies_per_user_per_day

    # ── Mention Fetching ────────────────────────────────────────────

    def fetch_new_mentions(self) -> list[dict]:
        """
        Fetch mentions since last processed ID.

        Returns:
            List of mention dicts with id, text, author_id, conversation_id,
            and referenced_tweets.
        """
        since_id = self._load_last_mention_id()

        logger.info(f"Fetching mentions (since_id={since_id})")

        kwargs = {
            "id": self.bot_user_id,
            "tweet_fields": ["conversation_id", "in_reply_to_user_id", "created_at"],
            "expansions": ["referenced_tweets.id", "author_id"],
            "max_results": 100,
        }
        if since_id:
            kwargs["since_id"] = since_id

        try:
            response = self.twitter.get_users_mentions(**kwargs)
        except Exception as e:
            logger.error(f"Error fetching mentions: {e}")
            return []

        if not response.data:
            logger.info("No new mentions found.")
            return []

        mentions = []
        for tweet in response.data:
            mentions.append({
                "id": str(tweet.id),
                "text": tweet.text,
                "author_id": str(tweet.author_id),
                "conversation_id": str(tweet.conversation_id),
                "in_reply_to_user_id": getattr(tweet, "in_reply_to_user_id", None),
                "created_at": str(tweet.created_at),
                "referenced_tweets": [
                    {"type": ref.type, "id": str(ref.id)}
                    for ref in (tweet.referenced_tweets or [])
                ],
            })

        # Save the newest mention ID so next poll starts after it
        newest_id = mentions[0]["id"]
        self._save_last_mention_id(newest_id)

        logger.info(f"Fetched {len(mentions)} new mentions")
        return mentions

    # ── Context Gathering ───────────────────────────────────────────

    def get_conversation_context(self, mention: dict) -> dict | None:
        """
        Get the parent tweet that the user replied to (our tweet).

        Args:
            mention: Mention dict from fetch_new_mentions

        Returns:
            Dict with 'parent_text' and 'parent_id', or None if not a reply
            to one of our tweets.
        """
        # Find the tweet this mention is replying to
        replied_to_id = None
        for ref in mention.get("referenced_tweets", []):
            if ref["type"] == "replied_to":
                replied_to_id = ref["id"]
                break

        if not replied_to_id:
            # Not a reply, just a direct mention — still worth replying to
            return {"parent_text": None, "parent_id": None}

        try:
            response = self.twitter.get_tweet(
                replied_to_id,
                tweet_fields=["author_id", "text", "conversation_id"],
            )
        except Exception as e:
            logger.error(f"Error fetching parent tweet {replied_to_id}: {e}")
            return None

        if not response.data:
            return None

        parent = response.data
        parent_author_id = str(parent.author_id)

        return {
            "parent_text": parent.text,
            "parent_id": str(parent.id),
            "is_reply_to_us": parent_author_id == self.bot_user_id,
        }

    # ── Filtering ───────────────────────────────────────────────────

    def should_reply(self, mention: dict) -> bool:
        """
        Decide whether to reply to this mention.

        Filters out:
        - Our own tweets
        - Rate-limited users (too many replies today)
        - Daily reply cap reached

        Args:
            mention: Mention dict

        Returns:
            True if we should reply
        """
        # Skip our own tweets
        if mention["author_id"] == self.bot_user_id:
            logger.info(f"Skipping mention {mention['id']} — it's our own tweet")
            return False

        history = self._load_reply_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_replies = [r for r in history["replies"] if r["date"] == today]

        # Check daily cap
        if len(today_replies) >= self.max_replies_per_day:
            logger.warning(f"Daily reply cap reached ({self.max_replies_per_day})")
            return False

        # Check per-user cap
        user_replies_today = [
            r for r in today_replies if r["author_id"] == mention["author_id"]
        ]
        if len(user_replies_today) >= self.max_replies_per_user_per_day:
            logger.info(
                f"Skipping mention {mention['id']} — "
                f"already replied {len(user_replies_today)} times to user today"
            )
            return False

        return True

    # ── Reply Generation ────────────────────────────────────────────

    def generate_reply(self, mention_text: str, parent_text: str | None) -> str:
        """
        Use Gemini to generate a reply in Nigerian Pidgin.

        Args:
            mention_text: The user's mention/reply text
            parent_text: Our original tweet they replied to (if any)

        Returns:
            Reply text (under 280 characters)
        """
        context_block = ""
        if parent_text:
            context_block = f'Your original tweet they replied to: "{parent_text}"\n'

        prompt = f"""You are Matta4Animals, an educational Twitter account about animal welfare.
You write in Nigerian Pidgin English, switching to English for scientific terms.

{context_block}Their reply/mention: "{mention_text}"

Generate a single reply tweet that:
- Is under 280 characters (STRICT LIMIT)
- Uses Nigerian Pidgin as base language, English for scientific terms
- Is friendly, educational, and informative
- Answers their question or acknowledges their point
- Does NOT include hashtags
- Does NOT start with @ (Twitter adds that automatically)

If they asked a question, answer it. If they made a point, engage with it.
If the mention is spam, trolling, or completely unrelated to animals, reply with a short friendly redirect to animal topics.

Return ONLY the reply text, nothing else. No quotes, no explanation."""

        try:
            response = self.gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            reply = response.text.strip().strip('"')

            # Hard enforce 280 char limit
            if len(reply) > 280:
                reply = reply[:277] + "..."

            logger.info(f"Generated reply ({len(reply)} chars): {reply}")
            return reply

        except Exception as e:
            logger.error(f"Error generating reply: {e}")
            return None

    # ── Posting ─────────────────────────────────────────────────────

    def post_reply(self, reply_text: str, in_reply_to_id: str) -> str | None:
        """
        Post a reply to a specific tweet.

        Args:
            reply_text: The reply text
            in_reply_to_id: Tweet ID to reply to

        Returns:
            The posted tweet's ID, or None on failure
        """
        try:
            response = self.twitter.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=in_reply_to_id,
            )
            tweet_id = response.data["id"]
            logger.info(f"Reply posted: ID {tweet_id}")
            return str(tweet_id)
        except Exception as e:
            logger.error(f"Error posting reply to {in_reply_to_id}: {e}")
            return None

    # ── Single Mention Processing ───────────────────────────────────

    def process_mention(self, mention: dict, dry_run: bool = False) -> bool:
        """
        Process a single mention end-to-end.

        Args:
            mention: Mention dict from fetch_new_mentions
            dry_run: If True, generate reply but don't post

        Returns:
            True if reply was posted (or would be in dry run)
        """
        mention_id = mention["id"]
        mention_text = mention["text"]
        author_id = mention["author_id"]

        logger.info(f"Processing mention {mention_id}: {mention_text[:80]}...")

        # Step 1: Should we reply?
        if not self.should_reply(mention):
            return False

        # Step 2: Get conversation context
        context = self.get_conversation_context(mention)
        if context is None:
            logger.warning(f"Could not get context for mention {mention_id}")
            return False

        parent_text = context.get("parent_text")

        # Step 3: Generate reply
        reply_text = self.generate_reply(mention_text, parent_text)
        if not reply_text:
            return False

        # Step 4: Post or preview
        if dry_run:
            logger.info(f"[DRY RUN] Would reply to {mention_id}:")
            logger.info(f"  Their text: {mention_text}")
            logger.info(f"  Our reply:  {reply_text} ({len(reply_text)} chars)")
        else:
            posted_id = self.post_reply(reply_text, mention_id)
            if not posted_id:
                return False

        # Step 5: Log to reply history
        self._add_to_reply_history(mention_id, author_id, reply_text)

        return True

    # ── Persistence Helpers ─────────────────────────────────────────

    def _load_last_mention_id(self) -> str | None:
        """Load the last processed mention ID from disk."""
        try:
            with open(LAST_MENTION_FILE, "r") as f:
                data = json.load(f)
                return data.get("last_mention_id")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_last_mention_id(self, mention_id: str):
        """Save the last processed mention ID to disk."""
        with open(LAST_MENTION_FILE, "w") as f:
            json.dump({"last_mention_id": mention_id}, f)

    def _load_reply_history(self) -> dict:
        """Load reply history from disk."""
        try:
            with open(REPLY_HISTORY_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"replies": []}

    def _add_to_reply_history(self, mention_id: str, author_id: str, reply_text: str):
        """Add a reply to the history file."""
        history = self._load_reply_history()
        history["replies"].append({
            "mention_id": mention_id,
            "author_id": author_id,
            "reply_text": reply_text,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep only last 30 days of history
        cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Simple approach: keep last 1000 entries max
        history["replies"] = history["replies"][-1000:]

        with open(REPLY_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
