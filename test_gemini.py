import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_gemini_api_key":
    print("Error: GOOGLE_API_KEY not found in .env file.")
    exit(1)

client = genai.Client(api_key=GOOGLE_API_KEY)


def test_generation():
    print("Testing Gemini Content Generation...")
    topics = ["animal advocacy", "AI safety", "factory farming"]

    for topic in topics:
        print(f"\nTopic: {topic}")
        prompt = f"Write a short, educational tweet about {topic} for a casual audience in Nigerian Pidgin English. Include 1 hashtag. Make it engaging and easy to understand."
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            print(f"Generated Tweet: {response.text.strip()}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    test_generation()
