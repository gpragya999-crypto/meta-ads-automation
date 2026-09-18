# -*- coding: utf-8 -*-
"""
End-to-end runner: scrape -> extract/download -> transcribe -> analyze -> report.

Examples:
    # Full pipeline for one brand + one or more competitors, in one go:
    python main.py run --tag mybrand \\
        --url "https://www.facebook.com/mybrandpage" \\
        --url "https://www.facebook.com/competitorpage" \\
        --limit 10 --active all

    # Or run steps one at a time (useful while testing / saving API credits):
    python -m src.scrape_ads --tag mybrand --url "..." --limit 10 --active all
    python -m src.extract_media --raw data/raw/mybrand_<timestamp>.json --tag mybrand
    python -m src.transcribe --tag mybrand
    python -m src.analyze --tag mybrand
    python -m src.report --tag mybrand
"""
import argparse

from src import scrape_ads, extract_media, transcribe, analyze, report


def cmd_run(args):
    items = scrape_ads.run_scraper(args.urls, args.limit, args.active)
    raw_path = scrape_ads.save_raw(items, args.tag)

    ads = extract_media.load_and_parse(raw_path)
    for ad in ads:
        ad["media_path"] = extract_media.download_media(ad)
    processed_path = extract_media.config.PROCESSED_DIR / f"{args.tag}_ads.json"
    import json
    processed_path.write_text(json.dumps(ads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved processed ads -> {processed_path}")

    if extract_media.config.OPENAI_API_KEY:
        _run_transcribe(args.tag)
    else:
        print("No OPENAI_API_KEY set — skipping transcription (image-only hook analysis will still run).")

    _run_analyze(args.tag, args.no_hook_analysis)
    md_path, csv_path = report.build_report(args.tag)
    print(f"\nDone. Report:\n  {md_path}\n  {csv_path}")


def _run_transcribe(tag):
    import sys
    old_argv = sys.argv
    sys.argv = ["transcribe.py", "--tag", tag]
    try:
        transcribe.main()
    finally:
        sys.argv = old_argv


def _run_analyze(tag, no_hook_analysis):
    import sys
    old_argv = sys.argv
    sys.argv = ["analyze.py", "--tag", tag] + (["--no-hook-analysis"] if no_hook_analysis else [])
    try:
        analyze.main()
    finally:
        sys.argv = old_argv


def main():
    parser = argparse.ArgumentParser(description="Meta Ads competitor-analysis pipeline.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the full pipeline end to end")
    p_run.add_argument("--tag", required=True)
    p_run.add_argument("--url", action="append", required=True, dest="urls")
    p_run.add_argument("--limit", type=int, default=10)
    p_run.add_argument("--active", choices=["all", "active", "inactive"], default="all")
    p_run.add_argument("--no-hook-analysis", action="store_true")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
