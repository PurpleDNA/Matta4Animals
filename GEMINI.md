# Matta4Animals Bot

A Python-based Twitter (X) bot that shares educational and surprising facts about animal ethics, protection, and future technologies (like AI) in Nigerian Pidgin English.

## Project Overview

- **Purpose:** To inform and provoke thought among a casual Nigerian audience regarding animal welfare and ethics.
- **Tech Stack:**
  - **Language:** Python 3.13
  - **LLM:** Google Gemini 2.0 Flash (via `google-genai`)
  - **Twitter API:** Tweepy (v2)
  - **Scheduling:** `schedule` library
  - **Environment:** `python-dotenv` for configuration

## Development Setup

1. **Environment:**
   - Create a virtual environment: `python -m venv venv`
   - Activate it: `.\venv\Scripts\activate` (Windows)
   - Install dependencies: `pip install -r requirements.txt`

2. **Configuration:**
   - Create a `.env` file based on `.env.example`.
   - Required keys: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`, `GOOGLE_API_KEY`.
   - `DRY_RUN`: Set to `True` for testing without posting to Twitter.
   - `POST_TIME`: HH:MM format for daily scheduling.

## Running the Bot

- **Scheduled Mode:** `python bot.py`
- **Test Mode (Run Once):** `python bot.py --once`

## Main Logic
- `bot.py`: Main entry point. Handles scheduling, content generation via Gemini, and posting via Tweepy.
- `test_gemini.py`: A utility script to test Gemini API connectivity and prompt performance.
