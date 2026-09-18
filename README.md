# Meta Ads Automation

Automated competitor-ad pipeline: scrape a brand's + competitors' Meta ads,
transcribe the videos, score every ad on public "winning signal" proxies,
run Claude hook analysis on each, and output a ranked report.

```
scrape (Apify) -> extract + download media -> transcribe (AssemblyAI) -> analyze (scoring + Claude) -> report (md/csv)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in APIFY_TOKEN, ASSEMBLYAI_API_KEY, ANTHROPIC_API_KEY
```

- **APIFY_TOKEN** — from https://console.apify.com/settings/integrations. Required to scrape.
- **ASSEMBLYAI_API_KEY** — from https://www.assemblyai.com/app/api-keys, used to transcribe ad videos. Skip and the pipeline still runs, just without transcripts (hook analysis falls back to ad copy only).
- **ANTHROPIC_API_KEY** — used for automatic hook analysis. Without it, `analyze.py` writes a ready-to-paste prompt file to `data/output/<tag>_hook_prompts.md` instead of calling the API.

## Run the full pipeline

```bash
python main.py run --tag mybrand \
  --url "https://www.facebook.com/mybrandpage" \
  --url "https://www.facebook.com/competitorpage" \
  --limit 10 --active all
```

Output lands in `data/output/<tag>_report_<timestamp>.md` and `.csv`.

## Or run each step manually (useful while testing)

```bash
python -m src.scrape_ads --tag mybrand --url "https://www.facebook.com/..." --limit 10 --active all
python -m src.extract_media --raw data/raw/mybrand_<timestamp>.json --tag mybrand
python -m src.transcribe --tag mybrand
python -m src.analyze --tag mybrand
python -m src.report --tag mybrand
```

## How "winning" is scored

Meta's public Ad Library doesn't expose real spend, ad-set counts, or
performance — so the score is built from the proxies that *are* public,
weighted in `config.py`:

- **Longevity** (45%) — days the ad has run. Advertisers kill losers fast; a
  long-running ad is very likely a winner.
- **Still active** (15%) — bonus if it's running right now.
- **Variation count** (25%) — how many near-duplicate creatives the same
  page is running in parallel. Multiple variants of the same concept is the
  public signature of "we found a winner and we're scaling/testing it,"
  standing in for the ad-set count you can't see from outside.
- **Platform spread** (15%) — how many placements (Facebook/Instagram/
  Audience Network/Messenger) it runs on.

Each ad also gets a Claude-generated **hook type**, the literal **hook
line**, and **why it works**, built from the ad copy + (if available) the
video transcript.

## Project layout

```
config.py              paths, weights, env vars
src/scrape_ads.py       Apify scrape -> data/raw/
src/extract_media.py    parse raw JSON, download videos/images -> data/media/
src/transcribe.py       AssemblyAI transcription -> data/transcripts/
src/analyze.py          winning-signal scoring + Claude hook analysis -> data/processed/
src/report.py           final ranked report -> data/output/
main.py                 orchestrates all 5 steps
```
