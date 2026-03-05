"""Story selection and history tracking."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from modules.models import ScoredStory

logger = logging.getLogger(__name__)


class StorySelector:
    """Selects best story and tracks posting history."""

    def __init__(self, history_file: str, history_days: int = 30, min_score: int = 50):
        """
        Initialize Story Selector.

        Args:
            history_file: Path to JSON file tracking posted stories
            history_days: Number of days to track history
            min_score: Minimum score threshold for stories
        """
        self.history_file = history_file
        self.history_days = history_days
        self.min_score = min_score
        self.history = self._load_history()

    def select_best_story(self, scored_stories: List[ScoredStory]) -> Optional[ScoredStory]:
        """
        Select the best story from scored list.

        Args:
            scored_stories: List of scored stories

        Returns:
            Best story that meets criteria, or None if no stories available
        """
        if not scored_stories:
            logger.warning("No stories to select from")
            return None

        # Sort by total score (descending)
        sorted_stories = sorted(scored_stories, key=lambda s: s.total_score, reverse=True)

        # Log top 5 scores
        logger.info("Top 5 story scores:")
        for i, story in enumerate(sorted_stories[:5], 1):
            logger.info(f"  {i}. [{story.total_score}] {story.title}")

        # Filter stories that meet minimum score OR get highest if none meet threshold
        qualifying_stories = [s for s in sorted_stories if s.total_score >= self.min_score]

        if not qualifying_stories:
            logger.warning(f"No stories scored >= {self.min_score}. Using highest-scoring story.")
            qualifying_stories = [sorted_stories[0]]

        # Try to select a story not in recent history
        for story in qualifying_stories:
            if not self.check_against_history(story):
                logger.info(f"Selected: {story.title} (score: {story.total_score})")
                return story

        # If all stories are in history, return the best one anyway
        best_story = qualifying_stories[0]
        logger.warning(f"All stories are in recent history. Using best: {best_story.title}")
        return best_story

    def check_against_history(self, story: ScoredStory) -> bool:
        """
        Check if story was recently posted.

        Args:
            story: Story to check

        Returns:
            True if story is in recent history, False otherwise
        """
        # Normalize title for comparison
        normalized_title = story.title.lower().strip()

        for posted_story in self.history.get('posted_stories', []):
            posted_title = posted_story.get('title', '').lower().strip()

            # Check for exact match or very similar titles
            if normalized_title == posted_title or normalized_title in posted_title or posted_title in normalized_title:
                logger.debug(f"Story '{story.title}' matches history: '{posted_story.get('title')}'")
                return True

        return False

    def add_to_history(self, story: ScoredStory) -> None:
        """
        Add a posted story to history.

        Args:
            story: Story that was posted
        """
        if 'posted_stories' not in self.history:
            self.history['posted_stories'] = []

        self.history['posted_stories'].append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'title': story.title,
            'source_url': story.link,
            'source': story.source,
            'score': story.total_score
        })

        # Clean old history
        self._clean_old_history()

        # Save to file
        self._save_history()

        logger.info(f"Added to history: {story.title}")

    def _load_history(self) -> dict:
        """Load history from JSON file."""
        if not os.path.exists(self.history_file):
            logger.info(f"History file not found. Creating new: {self.history_file}")
            return {'posted_stories': []}

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info(f"Loaded {len(history.get('posted_stories', []))} stories from history")
                return history
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            return {'posted_stories': []}

    def _save_history(self) -> None:
        """Save history to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)

            logger.debug("History saved successfully")
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def _clean_old_history(self) -> None:
        """Remove history entries older than history_days."""
        cutoff_date = datetime.now() - timedelta(days=self.history_days)

        original_count = len(self.history.get('posted_stories', []))

        self.history['posted_stories'] = [
            story for story in self.history.get('posted_stories', [])
            if datetime.strptime(story['date'], '%Y-%m-%d %H:%M:%S') >= cutoff_date
        ]

        removed_count = original_count - len(self.history['posted_stories'])
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old stories from history")
