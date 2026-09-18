# -*- coding: utf-8 -*-
"""Central config: API keys, paths, and tunable pipeline constants."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MEDIA_DIR = DATA_DIR / "media"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
OUTPUT_DIR = DATA_DIR / "output"

for d in (RAW_DIR, PROCESSED_DIR, MEDIA_DIR, TRANSCRIPTS_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "apify/facebook-ads-scraper")

# Winning-signal score weights (heuristic, tune freely) — must sum to ~1.0
WEIGHT_LONGEVITY = 0.45   # days an ad has been running (or ran) — longer = more likely a winner
WEIGHT_ACTIVE = 0.15      # bonus if the ad is still active right now
WEIGHT_VARIATIONS = 0.25  # how many similar creatives the same page is running (proxy for "scaling a winner")
WEIGHT_PLATFORMS = 0.15   # spread across FB/IG/AN/Messenger (proxy for scaled placement)

# Longevity (days) considered "maxed out" for scoring purposes
LONGEVITY_CAP_DAYS = 60

# Two ads from the same page count as "variations of the same creative" if
# their normalized body-text similarity is >= this ratio (0-1), or their
# titles match exactly.
VARIATION_SIMILARITY_THRESHOLD = 0.55
