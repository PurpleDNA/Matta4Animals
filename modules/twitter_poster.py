"""Twitter thread posting."""

import logging
import time
from typing import List

import tweepy

from modules.models import Thread

logger = logging.getLogger(__name__)


class TwitterPoster:
    """Posts threads to Twitter."""

    def __init__(self, twitter_client: tweepy.Client):
        """
        Initialize Twitter Poster.

        Args:
            twitter_client: Tweepy client for Twitter API v2
        """
        self.client = twitter_client

    def post_thread(self, thread: Thread) -> List[str]:
        """
        Post a thread to Twitter.

        Args:
            thread: Thread to post

        Returns:
            List of tweet IDs
        """
        logger.info(f"Posting {thread.thread_length}-tweet thread...")

        tweet_ids = []

        try:
            # Post first tweet
            logger.info(f"Posting tweet 1/{thread.thread_length}")
            first_response = self.client.create_tweet(text=thread.tweets[0])
            first_tweet_id = first_response.data['id']
            tweet_ids.append(first_tweet_id)
            logger.info(f"Tweet 1 posted: ID {first_tweet_id}")

            # Post remaining tweets as replies
            for i, tweet_text in enumerate(thread.tweets[1:], start=2):
                # Small delay to avoid rate limits
                time.sleep(2)

                logger.info(f"Posting tweet {i}/{thread.thread_length}")
                response = self.client.create_tweet(
                    text=tweet_text,
                    in_reply_to_tweet_id=tweet_ids[-1]
                )
                tweet_id = response.data['id']
                tweet_ids.append(tweet_id)
                logger.info(f"Tweet {i} posted: ID {tweet_id}")

            logger.info(f"Thread posted successfully! {len(tweet_ids)} tweets")
            return tweet_ids

        except Exception as e:
            logger.error(f"Error posting thread: {e}")
            if tweet_ids:
                logger.info(f"Partial thread posted: {len(tweet_ids)} tweets before error")
            raise

    def post_single_tweet(self, text: str) -> str:
        """
        Post a single tweet.

        Args:
            text: Tweet text

        Returns:
            Tweet ID
        """
        logger.info("Posting single tweet...")
        try:
            response = self.client.create_tweet(text=text)
            tweet_id = response.data['id']
            logger.info(f"Tweet posted: ID {tweet_id}")
            return tweet_id
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            raise
