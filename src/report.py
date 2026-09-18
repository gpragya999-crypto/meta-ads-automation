# -*- coding: utf-8 -*-
"""
Step 5: Build the final ranked report (Markdown + CSV) from analyzed ads.

CLI:
    python -m src.report --tag mybrand
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm")


def _media_html(media_path) -> str:
    """Embeds the downloaded ad video/image inline, served via the app's /media route."""
    if not media_path or not isinstance(media_path, str):
        return ""
    try:
        rel = Path(media_path).relative_to(config.MEDIA_DIR).as_posix()
    except ValueError:
        return ""
    url = f"/media/{rel}"
    if media_path.lower().endswith(VIDEO_EXTS):
        return f'<video controls preload="metadata" style="max-width:320px;border-radius:8px;display:block;margin:8px 0;" src="{url}"></video>'
    return f'<img src="{url}" style="max-width:320px;border-radius:8px;display:block;margin:8px 0;" alt="ad creative">'


def build_report(tag: str, is_sample: bool = False) -> tuple[str, str]:
    analyzed_path = config.PROCESSED_DIR / f"{tag}_analyzed.json"
    ads = json.loads(analyzed_path.read_text(encoding="utf-8"))

    df = pd.DataFrame(ads)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if "score_breakdown" in df.columns:
        for part in ("longevity", "active", "variations", "platforms"):
            df[f"score_breakdown_{part}"] = df["score_breakdown"].apply(
                lambda d, p=part: d.get(p, "") if isinstance(d, dict) else ""
            )

    csv_path = config.OUTPUT_DIR / f"{tag}_report_{ts}.csv"
    cols = ["page_name", "ad_id", "score",
            "score_breakdown_longevity", "score_breakdown_active",
            "score_breakdown_variations", "score_breakdown_platforms",
            "days_running", "variation_count", "is_active",
            "display_format", "publisher_platforms", "hook_type", "hook_line", "why_it_works",
            "body_text", "start_date", "end_date", "media_path"]
    cols = [c for c in cols if c in df.columns]
    df[cols].to_csv(csv_path, index=False)

    md_lines = [f"# Winning Creatives Report — {tag}", f"_Generated {ts}_", ""]
    if is_sample:
        md_lines.append(
            '<p style="background:#fef3c7;color:#92400e;padding:10px 14px;border-radius:6px;'
            'font-weight:600;">⚠️ SAMPLE DATA — this is bundled test data, not a real scrape. '
            'Uncheck "Use bundled sample data" and re-run to analyze real ads.</p>'
        )
        md_lines.append("")
    for page_name, group in df.groupby("page_name", sort=False):
        group = group.sort_values("score", ascending=False)
        md_lines.append(f"## {page_name}")
        for _, row in group.iterrows():
            md_lines.append(f"### #{row['ad_id']} — score {row['score']}/100")
            media_html = _media_html(row.get("media_path"))
            if media_html:
                md_lines.append(media_html)
            else:
                md_lines.append("_(no downloadable media for this ad)_")
            md_lines.append(
                f"- Running {row.get('days_running', 0)} day(s)"
                f"{' (still active)' if row.get('is_active') else ' (ended)'}"
                f" · {row.get('variation_count', 1)} similar variation(s) from this page"
                f" · platforms: {', '.join(row.get('publisher_platforms') or [])}"
            )
            breakdown = row.get("score_breakdown")
            if isinstance(breakdown, dict):
                items = "".join(
                    f"<li>{part.capitalize()}: {breakdown[part]}</li>"
                    for part in ("longevity", "active", "variations", "platforms")
                    if part in breakdown
                )
                md_lines.append(
                    f'<p><strong>Score breakdown ({row["score"]}/100 total):</strong></p><ul>{items}</ul>'
                )
            if row.get("hook_type"):
                md_lines.append(f"- **Hook type:** {row['hook_type']}")
            if row.get("hook_line"):
                md_lines.append(f"- **Hook line:** \"{row['hook_line']}\"")
            if row.get("why_it_works"):
                md_lines.append(f"- **Why it works:** {row['why_it_works']}")
            body = (row.get("body_text") or "").strip()
            if body:
                snippet = body[:200] + ("..." if len(body) > 200 else "")
                md_lines.append(f"- Ad copy: _{snippet}_")
            md_lines.append("")
        md_lines.append("")

    md_lines.append("## Overall top creatives (all pages)")
    top = df.sort_values("score", ascending=False).head(10)
    for i, (_, row) in enumerate(top.iterrows(), 1):
        md_lines.append(f"{i}. **{row['page_name']}** — #{row['ad_id']} (score {row['score']}/100)"
                         f"{': ' + row['hook_type'] if row.get('hook_type') else ''}")

    md_path = config.OUTPUT_DIR / f"{tag}_report_{ts}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return str(md_path), str(csv_path)


def main():
    parser = argparse.ArgumentParser(description="Build the final ranked winning-creatives report.")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()

    md_path, csv_path = build_report(args.tag)
    print(f"Report written:\n  {md_path}\n  {csv_path}")


if __name__ == "__main__":
    main()
