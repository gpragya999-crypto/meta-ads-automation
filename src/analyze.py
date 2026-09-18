# -*- coding: utf-8 -*-
"""
Step 4: Score every ad on "winning signals" and (optionally) run Claude hook
analysis on each one's copy + transcript.

Winning-signal heuristic (Meta's public Ad Library exposes no real ad-set
or performance data, so these are the standard public proxies):
  - longevity: how many days the ad has run — long-running ads are usually
    winners the advertiser hasn't turned off.
  - is_active: still running right now.
  - variation_count: how many near-identical creatives the same page is
    running in parallel — a proxy for "they're scaling a winning concept /
    testing multiple ad sets against it".
  - platform_spread: how many placements (FB/IG/Audience Network/Messenger)
    it runs on — broader spread usually follows a validated winner.

CLI:
    python -m src.analyze --tag mybrand
"""
import argparse
import json
import re
from datetime import date
from difflib import SequenceMatcher

from dateutil import parser as dateparser

import config

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

CLAUDE_MODEL = "claude-sonnet-5"

HOOK_PROMPT_TEMPLATE = """You are analyzing a competitor's Meta (Facebook/Instagram) ad to reverse-engineer why its hook works.

Page: {page_name}
Ad copy: {body_text}
Video transcript (first line(s) is the hook, if available): {transcript}

Respond in this exact format, nothing else:
Hook type: <one short label, e.g. bold claim / question / pattern interrupt / social proof / problem-agitate-solve / curiosity gap / price anchor>
Hook line: <the literal opening line/sentence used as the hook>
Why it works: <2-3 sentences, concrete>
"""


def _normalize(text: str) -> str:
    text = (text or "").lower()
    return re.sub(r"[^a-z0-9 ]+", "", text).strip()


def _parse_date(value):
    if not value:
        return None
    try:
        return dateparser.parse(str(value), fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def _is_same_creative(a: dict, b: dict) -> bool:
    title_a, title_b = _normalize(a.get("title")), _normalize(b.get("title"))
    if title_a and title_b and title_a == title_b:
        return True
    body_a, body_b = _normalize(a.get("body_text")), _normalize(b.get("body_text"))
    if not body_a or not body_b:
        return False
    return SequenceMatcher(None, body_a, body_b).ratio() >= config.VARIATION_SIMILARITY_THRESHOLD


def compute_variation_groups(ads: list[dict]) -> dict:
    """Maps ad_id -> size of the cluster of near-identical creatives the same
    page is running (matched by exact title or fuzzy body-text similarity)."""
    by_page: dict = {}
    for i, ad in enumerate(ads):
        by_page.setdefault(ad["page_id"] or ad["page_name"], []).append(i)

    sizes = {}
    for indices in by_page.values():
        parent = {i: i for i in indices}

        def find(i):
            while parent[i] != i:
                i = parent[i]
            return i

        for a_idx in range(len(indices)):
            for b_idx in range(a_idx + 1, len(indices)):
                i, j = indices[a_idx], indices[b_idx]
                if _is_same_creative(ads[i], ads[j]):
                    root_i, root_j = find(i), find(j)
                    if root_i != root_j:
                        parent[root_i] = root_j

        cluster_members: dict = {}
        for i in indices:
            cluster_members.setdefault(find(i), []).append(i)
        for members in cluster_members.values():
            for i in members:
                sizes[ads[i]["ad_id"]] = len(members)

    return sizes


def days_running(ad: dict, today: date) -> int:
    start = _parse_date(ad.get("start_date"))
    if not start:
        return 0
    end = today if ad.get("is_active") else (_parse_date(ad.get("end_date")) or today)
    return max((end - start).days, 0)


def winning_score(ad: dict, variation_size: int, today: date) -> dict:
    days = days_running(ad, today)
    n_platforms = len(ad.get("publisher_platforms") or [])

    longevity_frac = min(days / config.LONGEVITY_CAP_DAYS, 1.0)
    active_frac = 1.0 if ad.get("is_active") else 0.0
    variations_frac = min((variation_size - 1) / 4, 1.0)  # 0 extra variations -> 0, 4+ -> maxed
    platforms_frac = min(n_platforms / 4, 1.0)

    longevity_pts = config.WEIGHT_LONGEVITY * 100 * longevity_frac
    active_pts = config.WEIGHT_ACTIVE * 100 * active_frac
    variations_pts = config.WEIGHT_VARIATIONS * 100 * variations_frac
    platforms_pts = config.WEIGHT_PLATFORMS * 100 * platforms_frac
    score = longevity_pts + active_pts + variations_pts + platforms_pts

    return {
        "score": round(score, 1),
        "days_running": days,
        "variation_count": variation_size,
        "score_breakdown": {
            "longevity": f"{longevity_pts:.1f}/{config.WEIGHT_LONGEVITY * 100:.0f} pts "
                         f"({days} day(s) running, capped at {config.LONGEVITY_CAP_DAYS})",
            "active": f"{active_pts:.1f}/{config.WEIGHT_ACTIVE * 100:.0f} pts "
                      f"({'currently active' if ad.get('is_active') else 'ended'})",
            "variations": f"{variations_pts:.1f}/{config.WEIGHT_VARIATIONS * 100:.0f} pts "
                          f"({variation_size} similar creative(s) from this page, capped at 5)",
            "platforms": f"{platforms_pts:.1f}/{config.WEIGHT_PLATFORMS * 100:.0f} pts "
                         f"({n_platforms} placement(s): {', '.join(ad.get('publisher_platforms') or []) or 'none'})",
        },
    }


def run_hook_analysis(client, ad: dict, transcript: str) -> dict:
    prompt = HOOK_PROMPT_TEMPLATE.format(
        page_name=ad["page_name"],
        body_text=ad.get("body_text") or "(none)",
        transcript=transcript or "(no video / not transcribed)",
    )
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()

    parsed = {"hook_type": "", "hook_line": "", "why_it_works": ""}
    for line in text.splitlines():
        if line.lower().startswith("hook type:"):
            parsed["hook_type"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("hook line:"):
            parsed["hook_line"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("why it works:"):
            parsed["why_it_works"] = line.split(":", 1)[1].strip()
    return parsed


def main():
    parser = argparse.ArgumentParser(description="Score winning signals and run Claude hook analysis.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--no-hook-analysis", action="store_true",
                         help="Skip Claude hook analysis, only compute winning-signal scores")
    args = parser.parse_args()

    ads_path = config.PROCESSED_DIR / f"{args.tag}_ads.json"
    ads = json.loads(ads_path.read_text(encoding="utf-8"))

    transcripts_path = config.TRANSCRIPTS_DIR / f"{args.tag}_transcripts.json"
    transcripts = json.loads(transcripts_path.read_text(encoding="utf-8")) if transcripts_path.exists() else {}

    variation_sizes = compute_variation_groups(ads)
    today = date.today()

    use_claude = not args.no_hook_analysis and bool(config.ANTHROPIC_API_KEY) and Anthropic is not None
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY) if use_claude else None

    manual_prompts = []
    results = []

    for ad in ads:
        signals = winning_score(ad, variation_sizes[ad["ad_id"]], today)
        transcript = transcripts.get(ad["ad_id"], "")

        hook = {"hook_type": "", "hook_line": "", "why_it_works": ""}
        if use_claude:
            try:
                print(f"  analyzing hook for {ad['ad_id']} ({ad['page_name']})...")
                hook = run_hook_analysis(client, ad, transcript)
            except Exception as e:
                print(f"  ! Claude hook analysis failed for {ad['ad_id']}: {e}")
        elif not args.no_hook_analysis:
            manual_prompts.append(
                f"### {ad['page_name']} — {ad['ad_id']}\n"
                + HOOK_PROMPT_TEMPLATE.format(
                    page_name=ad["page_name"],
                    body_text=ad.get("body_text") or "(none)",
                    transcript=transcript or "(no video / not transcribed)",
                )
            )

        results.append({**ad, **signals, **hook})

    if manual_prompts:
        prompts_path = config.OUTPUT_DIR / f"{args.tag}_hook_prompts.md"
        prompts_path.write_text(
            "# Paste each block into Claude, then fill hook_type / hook_line / why_it_works back into the report by hand.\n\n"
            + "\n\n".join(manual_prompts),
            encoding="utf-8",
        )
        print(f"No ANTHROPIC_API_KEY set — wrote {len(manual_prompts)} ready-to-paste prompt(s) -> {prompts_path}")

    results.sort(key=lambda r: r["score"], reverse=True)

    out_path = config.PROCESSED_DIR / f"{args.tag}_analyzed.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(results)} scored ad(s) -> {out_path}")


if __name__ == "__main__":
    main()
