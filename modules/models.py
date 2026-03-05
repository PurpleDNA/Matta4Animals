"""Data models for Matta4Animals bot."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Story:
    """Raw story from RSS feed."""
    title: str
    link: str
    description: str
    published_date: datetime
    source: str


@dataclass
class ScoredStory(Story):
    """Story with scoring metadata."""
    educational_score: int = 0      # 0-30
    novelty_score: int = 0          # 0-20
    specificity_score: int = 0      # 0-15
    engagement_score: int = 0       # 0-10
    timeliness_score: int = 0       # 0-10 (auto-calculated)
    source_credibility_score: int = 0  # 0-10 (auto-calculated)
    story_type_bonus: int = 0       # 0-5 (auto-calculated)
    total_score: int = 0            # Sum of all
    reasoning: str = ""


@dataclass
class Thread:
    """Twitter thread data."""
    tweets: list[str]               # 1-10 tweets
    hashtags: list[str]             # Exactly 2 dynamic hashtags
    thread_length: int              # 1-10
    story: ScoredStory
    source_link: str
    reasoning_for_length: str = ""
