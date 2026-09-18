# -*- coding: utf-8 -*-
"""
Step 2: Turn raw Apify JSON into a clean, flat list of ads with:
  page name, ad id, copy text, format, dates, active flag, platforms, media urls.

Also downloads each ad's best available video (or falls back to an image)
into data/media/<page_slug>/<ad_id>.<ext>.

CLI:
    python -m src.extract_media --raw data/raw/mybrand_20260101T000000Z.json --tag mybrand
"""
import argparse
import json
import re
from pathlib import Path

import requests

import config


def _slug(text: str) -> str:
    text = (text or "unknown").strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "unknown"


def _first(*values):
    for v in values:
        if v:
            return v
    return None


def _extract_media_urls(snapshot: dict) -> tuple[list[str], list[str]]:
    """Returns (video_urls, image_urls), best quality first, deduped."""
    videos, images = [], []

    for v in snapshot.get("videos") or []:
        for key in ("videoHdUrl", "videoSdUrl"):
            if v.get(key):
                videos.append(v[key])
        if v.get("videoPreviewImageUrl"):
            images.append(v["videoPreviewImageUrl"])

    for c in snapshot.get("cards") or []:
        for key in ("videoHdUrl", "videoSdUrl"):
            if c.get(key):
                videos.append(c[key])
        for key in ("originalImageUrl", "resizedImageUrl", "videoPreviewImageUrl"):
            if c.get(key):
                images.append(c[key])

    # Plain single-image ads (displayFormat "IMAGE") put their image here,
    # not under "cards" — cards is [] for these.
    for img in snapshot.get("images") or []:
        for key in ("originalImageUrl", "resizedImageUrl"):
            if img.get(key):
                images.append(img[key])

    for key in ("originalImageUrl", "resizedImageUrl"):
        if snapshot.get(key):
            images.append(snapshot[key])

    dedup = lambda seq: list(dict.fromkeys(seq))
    return dedup(videos), dedup(images)


def parse_ad(item: dict) -> dict:
    snapshot = item.get("snapshot") or {}
    page = (item.get("pageInfo") or {}).get("page") or {}

    video_urls, image_urls = _extract_media_urls(snapshot)

    body_text = _first(
        (snapshot.get("body") or {}).get("text") if isinstance(snapshot.get("body"), dict) else snapshot.get("body"),
        snapshot.get("title"),
        snapshot.get("caption"),
    )

    return {
        "ad_id": str(_first(item.get("adArchiveId"), item.get("id"), item.get("adId"))),
        "page_name": _first(page.get("name"), item.get("pageName"), "unknown"),
        "page_id": _first(page.get("pageId"), item.get("pageId")),
        "title": snapshot.get("title"),
        "body_text": body_text or "",
        "display_format": snapshot.get("displayFormat"),
        "is_active": bool(_first(item.get("isActive"), snapshot.get("isActive"), False)),
        "start_date": _first(item.get("startDateFormatted"), item.get("startDate")),
        "end_date": _first(item.get("endDateFormatted"), item.get("endDate")),
        "publisher_platforms": item.get("publisherPlatform") or snapshot.get("publisherPlatform") or [],
        "spend": item.get("spend"),
        "reach_estimate": item.get("reachEstimate"),
        "video_urls": video_urls,
        "image_urls": image_urls,
    }


def load_and_parse(raw_path: str) -> list[dict]:
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    return [parse_ad(item) for item in raw]


def download_media(ad: dict) -> str | None:
    """Downloads the first available video (preferred) or image for an ad.
    Returns the local path, or None if nothing could be downloaded."""
    url = (ad["video_urls"] or ad["image_urls"] or [None])[0]
    if not url:
        return None

    is_video = url in ad["video_urls"]
    ext = "mp4" if is_video else "jpg"
    folder = config.MEDIA_DIR / _slug(ad["page_name"])
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / f"{_slug(ad['ad_id'])}.{ext}"

    if out_path.exists():
        return str(out_path)

    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        return str(out_path)
    except requests.RequestException as e:
        print(f"  ! failed to download media for ad {ad['ad_id']}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Extract ads + download media from a raw Apify scrape.")
    parser.add_argument("--raw", required=True, help="Path to raw JSON from scrape_ads.py")
    parser.add_argument("--tag", required=True, help="Label for the processed output file")
    parser.add_argument("--skip-download", action="store_true", help="Parse only, don't download media")
    args = parser.parse_args()

    ads = load_and_parse(args.raw)
    print(f"Parsed {len(ads)} ad(s) from {args.raw}")

    if not args.skip_download:
        for ad in ads:
            path = download_media(ad)
            ad["media_path"] = path
            status = path if path else "no media available"
            print(f"  [{ad['page_name']}] {ad['ad_id']} -> {status}")

    out_path = config.PROCESSED_DIR / f"{args.tag}_ads.json"
    out_path.write_text(json.dumps(ads, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved processed ads -> {out_path}")


if __name__ == "__main__":
    main()
