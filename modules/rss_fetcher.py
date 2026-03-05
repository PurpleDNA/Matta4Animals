"""RSS Feed fetching and parsing."""

import logging
from datetime import datetime, timedelta
from typing import List

import feedparser
from dateutil import parser as date_parser

from modules.models import Story

logger = logging.getLogger(__name__)


class RSSFeedManager:
    """Manages RSS feed fetching and parsing."""

    def __init__(self, feed_urls: List[str], fetch_hours: int = 48):
        """
        Initialize RSS Feed Manager.

        Args:
            feed_urls: List of RSS feed URLs to fetch from
            fetch_hours: How many hours back to fetch stories (default: 48)
        """
        self.feed_urls = feed_urls
        self.fetch_hours = fetch_hours
        self.stories = []

    def fetch_all_feeds(self) -> List[Story]:
        """
        Fetch and parse all RSS feeds.

        Returns:
            List of Story objects from all feeds
        """
        logger.info(f"Fetching {len(self.feed_urls)} RSS feeds...")
        all_stories = []

        for url in self.feed_urls:
            try:
                stories = self.parse_feed(url)
                all_stories.extend(stories)
                logger.info(f"Fetched {len(stories)} stories from {url}")
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                continue

        # Filter recent stories
        recent_stories = self.filter_recent_stories(all_stories)

        # Deduplicate
        unique_stories = self.deduplicate_stories(recent_stories)

        logger.info(f"Total unique recent stories: {len(unique_stories)}")
        return unique_stories

    def parse_feed(self, url: str) -> List[Story]:
        """
        Parse a single RSS feed.

        Args:
            url: RSS feed URL

        Returns:
            List of Story objects from this feed
        """
        stories = []
        feed = feedparser.parse(url)

        # Extract source name from URL
        source = self._extract_source_name(url)

        for entry in feed.entries:
            try:
                # Parse published date
                published_date = self._parse_date(entry)

                # Get description (try multiple fields)
                description = (
                    entry.get('summary', '') or
                    entry.get('description', '') or
                    entry.get('content', [{}])[0].get('value', '')
                )

                # Clean HTML tags from description
                description = self._clean_html(description)

                story = Story(
                    title=entry.get('title', 'Untitled'),
                    link=entry.get('link', ''),
                    description=description,
                    published_date=published_date,
                    source=source
                )
                stories.append(story)

            except Exception as e:
                logger.warning(f"Error parsing entry from {url}: {e}")
                continue

        return stories

    def filter_recent_stories(self, stories: List[Story]) -> List[Story]:
        """
        Filter stories to only include recent ones.

        Args:
            stories: List of all stories

        Returns:
            List of stories published within fetch_hours
        """
        from datetime import timezone

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.fetch_hours)

        recent = []
        for s in stories:
            # Make published_date timezone-aware if it's naive
            pub_date = s.published_date
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)

            if pub_date >= cutoff_time:
                recent.append(s)

        logger.info(f"Filtered to {len(recent)} stories from last {self.fetch_hours} hours")
        return recent

    def deduplicate_stories(self, stories: List[Story]) -> List[Story]:
        """
        Remove duplicate stories based on title similarity.

        Args:
            stories: List of stories

        Returns:
            List of unique stories
        """
        seen_titles = set()
        unique_stories = []

        for story in stories:
            # Normalize title for comparison (lowercase, strip whitespace)
            normalized_title = story.title.lower().strip()

            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_stories.append(story)

        logger.info(f"Removed {len(stories) - len(unique_stories)} duplicates")
        return unique_stories

    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL."""
        # Remove protocol
        url = url.replace('https://', '').replace('http://', '')
        # Get domain
        domain = url.split('/')[0]
        # Remove www.
        domain = domain.replace('www.', '')
        return domain

    def _parse_date(self, entry) -> datetime:
        """Parse published date from entry."""
        date_string = entry.get('published', entry.get('updated', ''))

        if date_string:
            try:
                return date_parser.parse(date_string)
            except Exception:
                pass

        # Fallback to current time if no date found
        return datetime.now()

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
