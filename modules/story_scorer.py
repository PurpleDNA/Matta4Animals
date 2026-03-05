"""Story scoring system using Gemini."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List

from google import genai

from modules.models import Story, ScoredStory

logger = logging.getLogger(__name__)


class StoryScorer:
    """Scores stories based on multiple criteria."""

    def __init__(self, client: genai.Client, source_credibility: Dict[str, int],
                 story_type_keywords: Dict[str, List[str]]):
        """
        Initialize Story Scorer.

        Args:
            client: Gemini client
            source_credibility: Dictionary mapping source domains to credibility scores
            story_type_keywords: Dictionary of story types and their keywords
        """
        self.client = client
        self.source_credibility = source_credibility
        self.story_type_keywords = story_type_keywords

    def score_all_stories(self, stories: List[Story], max_workers: int = 10) -> List[ScoredStory]:
        """
        Score all stories concurrently using a thread pool.

        Args:
            stories: List of stories to score
            max_workers: Number of parallel Gemini requests (default: 10)

        Returns:
            List of ScoredStory objects
        """
        logger.info(f"Scoring {len(stories)} stories with {max_workers} workers...")
        scored = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.score_story, story): story for story in stories}
            for future in as_completed(futures):
                try:
                    scored.append(future.result())
                except Exception as e:
                    logger.error(f"Error scoring story: {e}")

        return scored

    def score_story(self, story: Story) -> ScoredStory:
        """
        Score a story using Gemini and automatic criteria.

        Args:
            story: Story to score

        Returns:
            ScoredStory with all scores calculated
        """
        logger.info(f"Scoring story: {story.title}")

        # Get Gemini scores (educational, novelty, specificity, engagement)
        gemini_scores = self._get_gemini_scores(story)

        # Calculate automatic scores
        timeliness_score = self._calculate_timeliness_score(story.published_date)
        source_credibility_score = self._get_source_credibility_score(story.source)
        story_type_bonus = self._calculate_story_type_bonus(story)

        # Calculate total
        total_score = (
            gemini_scores['educational_score'] +
            gemini_scores['novelty_score'] +
            gemini_scores['specificity_score'] +
            gemini_scores['engagement_score'] +
            timeliness_score +
            source_credibility_score +
            story_type_bonus
        )

        scored_story = ScoredStory(
            title=story.title,
            link=story.link,
            description=story.description,
            published_date=story.published_date,
            source=story.source,
            educational_score=gemini_scores['educational_score'],
            novelty_score=gemini_scores['novelty_score'],
            specificity_score=gemini_scores['specificity_score'],
            engagement_score=gemini_scores['engagement_score'],
            timeliness_score=timeliness_score,
            source_credibility_score=source_credibility_score,
            story_type_bonus=story_type_bonus,
            total_score=total_score,
            reasoning=gemini_scores['reasoning']
        )

        logger.info(f"Total score: {total_score} | {scored_story.reasoning}")
        return scored_story

    def _get_gemini_scores(self, story: Story) -> Dict:
        """
        Get scores from Gemini for educational, novelty, specificity, engagement.

        Args:
            story: Story to score

        Returns:
            Dictionary with scores and reasoning
        """
        prompt = f"""You are scoring animal-related stories for an educational Twitter account (Matta4Animals).

Story Title: {story.title}
RSS Description: {story.description}
Source: {story.source}
Published: {story.published_date.strftime('%Y-%m-%d %H:%M')}

Score this story (0-100) based on:

1. Educational Value (0-30): What specific new knowledge does the RSS description suggest? Does it teach about animal suffering, welfare, behavior, or biology?
2. Novelty (0-20): How rare/unique is this event or information? Is it breaking news, first-time occurrence, or new discovery?
3. Specificity (0-15): How concrete and detailed is the description? Are there named locations, species, organizations, or documented evidence?
4. Engagement (0-10): How compelling is this for a general audience? Is it emotionally resonant (without being exploitative) and shareable?

Return ONLY valid JSON in this exact format:
{{
  "educational_score": <int 0-30>,
  "novelty_score": <int 0-20>,
  "specificity_score": <int 0-15>,
  "engagement_score": <int 0-10>,
  "reasoning": "<2-3 sentences explaining the scores>"
}}"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )

            # Extract JSON from response
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            scores = json.loads(response_text)

            # Validate scores are within bounds
            scores['educational_score'] = min(30, max(0, scores.get('educational_score', 0)))
            scores['novelty_score'] = min(20, max(0, scores.get('novelty_score', 0)))
            scores['specificity_score'] = min(15, max(0, scores.get('specificity_score', 0)))
            scores['engagement_score'] = min(10, max(0, scores.get('engagement_score', 0)))

            return scores

        except Exception as e:
            logger.error(f"Error getting Gemini scores: {e}")
            # Return default low scores
            return {
                'educational_score': 10,
                'novelty_score': 5,
                'specificity_score': 5,
                'engagement_score': 3,
                'reasoning': f"Error during scoring: {str(e)}"
            }

    def _calculate_timeliness_score(self, published_date: datetime) -> int:
        """
        Calculate timeliness score based on how recent the story is.

        Args:
            published_date: When the story was published

        Returns:
            Score from 0-10
        """
        from datetime import timezone

        # Make both dates timezone-aware for comparison
        now = datetime.now(timezone.utc)
        pub_date = published_date
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)

        hours_old = (now - pub_date).total_seconds() / 3600

        if hours_old <= 24:
            score = 10
        elif hours_old <= 48:
            score = 7
        elif hours_old <= 72:
            score = 4
        else:
            score = 2

        logger.debug(f"Timeliness score: {score} ({hours_old:.1f} hours old)")
        return score

    def _get_source_credibility_score(self, source: str) -> int:
        """
        Get source credibility score from lookup table.

        Args:
            source: Source domain

        Returns:
            Score from 0-10
        """
        score = self.source_credibility.get(source, 6)  # Default to 6 if unknown
        logger.debug(f"Source credibility score for {source}: {score}")
        return score

    def _calculate_story_type_bonus(self, story: Story) -> int:
        """
        Calculate bonus points based on story type.

        Args:
            story: Story to analyze

        Returns:
            Bonus score from 0-5
        """
        text = (story.title + " " + story.description).lower()
        bonus = 0

        # Check for story type keywords
        for story_type, keywords in self.story_type_keywords.items():
            if any(keyword.lower() in text for keyword in keywords):
                if story_type == 'wildlife_behavior':
                    bonus = max(bonus, 5)
                elif story_type == 'conservation':
                    bonus = max(bonus, 4)
                elif story_type == 'industry_exposure':
                    bonus = max(bonus, 4)
                elif story_type == 'scientific':
                    bonus = max(bonus, 3)
                elif story_type == 'viral_event':
                    bonus = max(bonus, 5)

        logger.debug(f"Story type bonus: {bonus}")
        return bonus
