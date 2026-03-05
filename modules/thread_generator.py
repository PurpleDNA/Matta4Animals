"""Twitter thread generation using Gemini."""

import json
import logging

from google import genai

from modules.models import ScoredStory, Thread

logger = logging.getLogger(__name__)


class ThreadGenerator:
    """Generates Twitter threads in Nigerian Pidgin."""

    def __init__(self, client: genai.Client, max_thread_length: int = 10):
        """
        Initialize Thread Generator.

        Args:
            client: Gemini client
            max_thread_length: Maximum number of tweets per thread
        """
        self.client = client
        self.max_thread_length = max_thread_length

    def generate_thread(self, story: ScoredStory) -> Thread:
        """
        Generate a Twitter thread for the story.

        Args:
            story: Story to create thread for

        Returns:
            Thread object with tweets and metadata
        """
        logger.info(f"Generating thread for: {story.title}")

        prompt = self._build_prompt(story)

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            # Parse response
            thread_data = self._parse_response(response.text)

            # Validate and create thread
            thread = Thread(
                tweets=thread_data['tweets'][:self.max_thread_length],
                hashtags=thread_data['hashtags'][:2],  # Strictly 2 hashtags
                thread_length=len(thread_data['tweets'][:self.max_thread_length]),
                story=story,
                source_link=story.link,
                reasoning_for_length=thread_data.get('reasoning_for_length', '')
            )

            logger.info(f"Generated {thread.thread_length}-tweet thread with hashtags: {thread.hashtags}")
            return thread

        except Exception as e:
            logger.error(f"Error generating thread: {e}")
            # Fallback to simple single tweet
            return self._create_fallback_thread(story)

    def _build_prompt(self, story: ScoredStory) -> str:
        """Build the Gemini prompt for thread generation."""
        prompt = f"""You are Matta4Animals, an educational Twitter account sharing animal stories in Nigerian Pidgin English.

Story Title: {story.title}
Description: {story.description}
Source Link: {story.link}

TASK:
1. Determine how many tweets (1-10) this story needs based on:
   - How much educational content is in the story
   - Complexity of the topic
   - Natural narrative flow

2. Generate a Twitter thread that:
   - Uses Nigerian Pidgin as the base language
   - Switches to English for complex scientific terms (keep Pidgin framing)
   - Educates people about what's happening to animals
   - Is informative without being overly graphic
   - Each tweet is under 280 characters
   - Include source link in THE FIRST TWEET naturally
   - Add exactly 2 dynamic hashtags in THE LAST TWEET ONLY

3. Create exactly 2 hashtags based on story content (not generic)

TONE: Educational, informative, accessible

Return ONLY valid JSON in this exact format:
{{
  "thread_length": <int 1-10>,
  "tweets": [
    "tweet 1 text with {story.link}",
    "tweet 2 text",
    ...
    "final tweet text #HashTag1 #HashTag2"
  ],
  "hashtags": ["#HashTag1", "#HashTag2"],
  "reasoning_for_length": "<brief explanation>"
}}

EXAMPLES:

Example 1 (Single tweet):
{{
  "thread_length": 1,
  "tweets": [
    "Flying squirrels no dey bite humans well well. {story.link} Dem get gliding membrane (patagium) wey stretch from hand reach ankle, so dem prefer to escape than attack. #WildlifeFacts #AnimalBehavior"
  ],
  "hashtags": ["#WildlifeFacts", "#AnimalBehavior"],
  "reasoning_for_length": "Simple fact that fits in one clear tweet"
}}

Example 2 (3-tweet thread):
{{
  "thread_length": 3,
  "tweets": [
    "For di first time in recorded history, snow leopard don attack human being. {story.link} This thing never happen before for all di years wey scientists don dey study dem.",
    "Climate change and habitat destruction fit be di reason wey push this apex predator close to human settlements. As their natural prey dey disappear, dem dey forced to look for food for new places.",
    "This na serious warning say when we destroy animal habitat, we go see more desperate and unusual behavior from wildlife. #Conservation #ClimateImpact"
  ],
  "hashtags": ["#Conservation", "#ClimateImpact"],
  "reasoning_for_length": "Breaking news needs context and explanation of causes/implications"
}}

Example 3 (2-tweet thread with scientific terms):
{{
  "thread_length": 2,
  "tweets": [
    "New study don show say octopuses fit feel pain through nociceptors just like humans. {story.link} Researchers observe say dem dey avoid places wey dem experience pain and dem dey nurse injured arms.",
    "This discovery dey challenge how fishing industry dey treat cephalopods. Many countries never get laws to protect dem even though dem get complex nervous systems. #MarineLife #AnimalWelfare"
  ],
  "hashtags": ["#MarineLife", "#AnimalWelfare"],
  "reasoning_for_length": "Scientific finding needs one tweet for discovery, one for implications"
}}"""

        return prompt

    def _parse_response(self, response_text: str) -> dict:
        """Parse Gemini's JSON response."""
        # Remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()

        # Parse JSON
        data = json.loads(response_text)

        # Validate structure
        if 'tweets' not in data or 'hashtags' not in data:
            raise ValueError("Invalid response structure from Gemini")

        # Ensure tweets is a list
        if not isinstance(data['tweets'], list) or len(data['tweets']) == 0:
            raise ValueError("No tweets generated")

        # Ensure hashtags is a list with exactly 2 items
        if not isinstance(data['hashtags'], list):
            data['hashtags'] = []

        # Make sure we have exactly 2 hashtags
        while len(data['hashtags']) < 2:
            data['hashtags'].append('#AnimalRights')

        data['hashtags'] = data['hashtags'][:2]

        return data

    def _create_fallback_thread(self, story: ScoredStory) -> Thread:
        """Create a simple fallback thread if generation fails."""
        logger.warning("Using fallback thread generation")

        tweet = f"{story.title} {story.link} #AnimalNews #Wildlife"

        # Truncate if too long
        if len(tweet) > 280:
            max_title_length = 280 - len(story.link) - len(" ... #AnimalNews #Wildlife") - 3
            truncated_title = story.title[:max_title_length]
            tweet = f"{truncated_title}... {story.link} #AnimalNews #Wildlife"

        return Thread(
            tweets=[tweet],
            hashtags=["#AnimalNews", "#Wildlife"],
            thread_length=1,
            story=story,
            source_link=story.link,
            reasoning_for_length="Fallback due to generation error"
        )
