# -*- coding: utf-8 -*-
"""
Step 1: Scrape Meta Ad Library via the Apify actor "apify/facebook-ads-scraper".

CLI:
    python -m src.scrape_ads --tag mybrand --url "https://www.facebook.com/<page>" \
        --url "https://www.facebook.com/<competitor>" --limit 10 --active all

Saves the raw actor output to data/raw/<tag>_<timestamp>.json and returns it.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from apify_client import ApifyClient

import config


def build_run_input(urls: list[str], results_limit: int = 10, active_status: str = "all") -> dict:
    """active_status: 'all' | 'active' | 'inactive' (mirrors the Apify actor's own options).

    Field names/values match apify/facebook-ads-scraper's actual input schema
    (confirmed via its build's actorDefinition.input — 'startUrls' as an
    array of {url}, 'resultsLimit' as int, 'activeStatus' as '' | 'active' | 'inactive').
    """
    status_map = {"all": "", "active": "active", "inactive": "inactive"}
    return {
        "startUrls": [{"url": u} for u in urls],
        "resultsLimit": results_limit,
        "activeStatus": status_map.get(active_status, ""),
    }


def run_scraper(urls: list[str], results_limit: int = 10, active_status: str = "all") -> list[dict]:
    if not config.APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN is not set. Copy .env.example to .env and fill it in.")
    if not urls:
        raise ValueError("Need at least one Facebook Page / Ad Library URL to scrape.")

    client = ApifyClient(config.APIFY_TOKEN)
    run_input = build_run_input(urls, results_limit, active_status)

    print(f"Starting Apify actor '{config.APIFY_ACTOR_ID}' for {len(urls)} URL(s)...")
    run = client.actor(config.APIFY_ACTOR_ID).call(run_input=run_input)

    items = list(client.dataset(run.default_dataset_id).iterate_items())
    print(f"Run finished. Pulled {len(items)} ad record(s).")
    return items


def save_raw(items: list[dict], tag: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = config.RAW_DIR / f"{tag}_{ts}.json"
    out_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved raw scrape -> {out_path}")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Scrape Meta Ad Library via Apify.")
    parser.add_argument("--tag", required=True, help="Short label for this scrape, e.g. brand name")
    parser.add_argument("--url", action="append", required=True, dest="urls",
                         help="Facebook Page or Ad Library URL. Repeat --url for each brand/competitor.")
    parser.add_argument("--limit", type=int, default=10, help="Results limit per URL (default 10)")
    parser.add_argument("--active", choices=["all", "active", "inactive"], default="all")
    args = parser.parse_args()

    items = run_scraper(args.urls, args.limit, args.active)
    if not items:
        print("No ads returned. Try --active all, or double-check the URL.", file=sys.stderr)
    save_raw(items, args.tag)


if __name__ == "__main__":
    main()
