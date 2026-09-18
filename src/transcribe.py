# -*- coding: utf-8 -*-
"""
Step 3: Transcribe downloaded ad videos with the AssemblyAI API.

Flow per video: upload the local file -> submit a transcription job for the
returned upload_url -> poll until it completes -> read back the text.

Image-only ads (no video) are skipped here — their body_text alone feeds
the hook analysis in analyze.py.

CLI:
    python -m src.transcribe --tag mybrand
"""
import argparse
import json
import time

import requests

import config

UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300


def _auth_headers() -> dict:
    return {"authorization": config.ASSEMBLYAI_API_KEY}


def transcribe_file(media_path: str) -> str:
    with open(media_path, "rb") as f:
        upload_resp = requests.post(UPLOAD_URL, headers=_auth_headers(), data=f, timeout=120)
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]

    submit_resp = requests.post(
        TRANSCRIPT_URL,
        headers={**_auth_headers(), "content-type": "application/json"},
        json={"audio_url": upload_url},
        timeout=30,
    )
    submit_resp.raise_for_status()
    transcript_id = submit_resp.json()["id"]

    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        poll_resp = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=_auth_headers(), timeout=30)
        poll_resp.raise_for_status()
        result = poll_resp.json()
        if result["status"] == "completed":
            return result["text"] or ""
        if result["status"] == "error":
            raise RuntimeError(result.get("error", "AssemblyAI transcription failed"))
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Transcription {transcript_id} did not finish within {POLL_TIMEOUT_SECONDS}s")


def main():
    parser = argparse.ArgumentParser(description="Transcribe ad videos via AssemblyAI.")
    parser.add_argument("--tag", required=True, help="Same tag used in extract_media.py")
    args = parser.parse_args()

    if not config.ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set. Add it to your .env file.")

    ads_path = config.PROCESSED_DIR / f"{args.tag}_ads.json"
    ads = json.loads(ads_path.read_text(encoding="utf-8"))

    transcripts = {}
    existing_path = config.TRANSCRIPTS_DIR / f"{args.tag}_transcripts.json"
    if existing_path.exists():
        transcripts = json.loads(existing_path.read_text(encoding="utf-8"))

    for ad in ads:
        media_path = ad.get("media_path")
        if not media_path or not media_path.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            continue
        if ad["ad_id"] in transcripts:
            print(f"  [skip, cached] {ad['ad_id']}")
            continue
        try:
            print(f"  transcribing {ad['ad_id']} ({ad['page_name']})...")
            text = transcribe_file(media_path)
            transcripts[ad["ad_id"]] = text.strip()
        except Exception as e:
            print(f"  ! failed to transcribe {ad['ad_id']}: {e}")

    existing_path.write_text(json.dumps(transcripts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(transcripts)} transcript(s) -> {existing_path}")


if __name__ == "__main__":
    main()
