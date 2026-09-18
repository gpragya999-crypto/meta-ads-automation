# -*- coding: utf-8 -*-
"""
Local web UI for the Meta Ads Automation pipeline.

Run:
    python app.py

Then open http://127.0.0.1:5000 in a browser.
"""
import io
import json
import sys
import threading
import traceback
import uuid
from pathlib import Path

import markdown as md
from flask import Flask, request, redirect, url_for, render_template, flash, jsonify, Response, send_from_directory

import config
from src import scrape_ads, extract_media, transcribe as transcribe_mod, analyze as analyze_mod, report as report_mod
from src.sample_data import SAMPLE_RAW_ADS

app = Flask(__name__)
app.secret_key = "local-dev-only"  # single-user local tool, not exposed to the internet

RUNS = {}          # run_id -> {"status", "log", "tag", "error"}
RUN_LOCK = threading.Lock()
_pipeline_busy = threading.Lock()


class _RunLogStream(io.TextIOBase):
    def __init__(self, run_id):
        self.run_id = run_id

    def write(self, s):
        if s.strip():
            with RUN_LOCK:
                RUNS[self.run_id]["log"].append(s.rstrip())
        return len(s)


def _run_module_main(main_func, argv):
    old_argv = sys.argv
    sys.argv = ["_"] + argv
    try:
        main_func()
    finally:
        sys.argv = old_argv


def _pipeline_worker(run_id, tag, urls, limit, active, use_sample, skip_transcribe, skip_hooks):
    run = RUNS[run_id]
    old_stdout = sys.stdout
    sys.stdout = _RunLogStream(run_id)
    try:
        with _pipeline_busy:
            if use_sample:
                print("Using bundled sample data — no API keys needed (still downloads small public sample media).")
                raw_path = config.RAW_DIR / f"{tag}_sample.json"
                raw_path.write_text(json.dumps(SAMPLE_RAW_ADS, indent=2), encoding="utf-8")
            else:
                items = scrape_ads.run_scraper(urls, limit, active)
                raw_path = Path(scrape_ads.save_raw(items, tag))

            ads = extract_media.load_and_parse(str(raw_path))
            for ad in ads:
                ad["media_path"] = extract_media.download_media(ad)
            processed_path = config.PROCESSED_DIR / f"{tag}_ads.json"
            processed_path.write_text(json.dumps(ads, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Saved processed ads -> {processed_path}")

            if not use_sample and not skip_transcribe and config.ASSEMBLYAI_API_KEY:
                _run_module_main(transcribe_mod.main, ["--tag", tag])
            else:
                print("Skipping transcription.")

            # Note: only an *explicit* skip_hooks disables the manual-prompt
            # fallback too. Missing ANTHROPIC_API_KEY alone should still
            # produce the paste-into-Claude prompts file, not silence both.
            analyze_argv = ["--tag", tag]
            if use_sample or skip_hooks:
                analyze_argv.append("--no-hook-analysis")
            _run_module_main(analyze_mod.main, analyze_argv)

            report_mod.build_report(tag, is_sample=use_sample)
            print("Pipeline finished.")
            run["status"] = "done"
    except Exception as e:
        run["status"] = "error"
        run["error"] = str(e)
        print(f"ERROR: {e}")
        print(traceback.format_exc())
    finally:
        sys.stdout = old_stdout


@app.route("/")
def index():
    return render_template(
        "index.html",
        has_apify_key=bool(config.APIFY_TOKEN),
        has_assemblyai_key=bool(config.ASSEMBLYAI_API_KEY),
        has_anthropic_key=bool(config.ANTHROPIC_API_KEY),
    )


@app.route("/media/<path:filepath>")
def media(filepath):
    """Serves downloaded ad media (data/media/...) so the report can show real
    video/image previews in the browser."""
    return send_from_directory(str(config.MEDIA_DIR), filepath)


@app.route("/run", methods=["POST"])
def run_pipeline():
    tag = (request.form.get("tag") or "run").strip() or "run"
    tag = "".join(c if c.isalnum() or c in "-_" else "-" for c in tag)
    use_sample = request.form.get("use_sample") == "1"
    urls = [u.strip() for u in (request.form.get("urls") or "").splitlines() if u.strip()]
    limit = int(request.form.get("limit") or 10)
    active = request.form.get("active") or "all"
    skip_transcribe = request.form.get("skip_transcribe") == "1"
    skip_hooks = request.form.get("skip_hooks") == "1"

    if use_sample and urls:
        # Real URLs were typed in — that's a stronger signal than a checkbox
        # that may have been left checked from a stale page load. Don't
        # silently run fake data when the user clearly gave us real input.
        use_sample = False
        flash("Note: real URLs were provided, so this ran as a live scrape, not sample data.")

    if not use_sample:
        if not config.APIFY_TOKEN:
            flash("APIFY_TOKEN is not set — add it on the Settings page, or use the sample-data test mode.")
            return redirect(url_for("index"))
        if not urls:
            flash("Add at least one Facebook Page / Ad Library URL, or use the sample-data test mode.")
            return redirect(url_for("index"))

    if _pipeline_busy.locked():
        flash("Another pipeline run is already in progress — wait for it to finish.")
        return redirect(url_for("index"))

    run_id = uuid.uuid4().hex
    RUNS[run_id] = {"status": "running", "log": [], "tag": tag, "error": None}

    thread = threading.Thread(
        target=_pipeline_worker,
        args=(run_id, tag, urls, limit, active, use_sample, skip_transcribe, skip_hooks),
        daemon=True,
    )
    thread.start()
    return redirect(url_for("run_status", run_id=run_id))


@app.route("/status/<run_id>")
def run_status(run_id):
    run = RUNS.get(run_id)
    if not run:
        flash("Unknown run id.")
        return redirect(url_for("index"))
    return render_template("status.html", run_id=run_id, tag=run["tag"])


@app.route("/api/status/<run_id>")
def api_status(run_id):
    run = RUNS.get(run_id)
    if not run:
        return jsonify({"status": "error", "log": ["Unknown run id"], "tag": ""}), 404
    return jsonify({"status": run["status"], "log": run["log"], "tag": run["tag"], "error": run["error"]})


def _latest_report_paths(tag: str):
    candidates = sorted(config.OUTPUT_DIR.glob(f"{tag}_report_*.md"))
    if not candidates:
        return None, None
    md_path = candidates[-1]
    csv_path = md_path.with_suffix(".csv")
    return md_path, (csv_path if csv_path.exists() else None)


@app.route("/report/<tag>")
def view_report(tag):
    md_path, _ = _latest_report_paths(tag)
    if not md_path:
        flash(f"No report found yet for '{tag}'.")
        return redirect(url_for("index"))
    report_html = md.markdown(md_path.read_text(encoding="utf-8"))
    has_hook_prompts = (config.OUTPUT_DIR / f"{tag}_hook_prompts.md").exists()
    return render_template("report.html", tag=tag, report_html=report_html, has_hook_prompts=has_hook_prompts)


@app.route("/report/<tag>/hook-prompts")
def hook_prompts(tag):
    path = config.OUTPUT_DIR / f"{tag}_hook_prompts.md"
    if not path.exists():
        flash(f"No hook-analysis prompts file for '{tag}'.")
        return redirect(url_for("view_report", tag=tag))
    report_html = md.markdown(path.read_text(encoding="utf-8"))
    return render_template("report.html", tag=f"{tag} — hook-analysis prompts", report_html=report_html, has_hook_prompts=False)


@app.route("/report/<tag>/download.<kind>")
def download_report(tag, kind):
    md_path, csv_path = _latest_report_paths(tag)
    target = md_path if kind == "md" else csv_path
    if not target or not target.exists():
        flash("Report file not found.")
        return redirect(url_for("index"))
    mimetype = "text/markdown" if kind == "md" else "text/csv"
    return Response(target.read_text(encoding="utf-8"), mimetype=mimetype,
                     headers={"Content-Disposition": f"attachment; filename={target.name}"})


@app.route("/reports")
def reports():
    seen = {}
    for path in sorted(config.OUTPUT_DIR.glob("*_report_*.md")):
        tag = path.name.split("_report_")[0]
        seen[tag] = path.stem.split("_report_")[-1]
    tags = sorted(seen.items())
    return render_template("reports.html", tags=tags)


ENV_KEYS = ["APIFY_TOKEN", "ASSEMBLYAI_API_KEY", "ANTHROPIC_API_KEY"]


@app.route("/settings", methods=["GET", "POST"])
def settings():
    env_path = config.ROOT / ".env"
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    if request.method == "POST":
        for key in ENV_KEYS:
            new_val = (request.form.get(key) or "").strip()
            if new_val:
                existing[key] = new_val
        lines = [f"{k}={v}" for k, v in existing.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        flash("Saved. Restart the server for changed keys to take effect.")
        return redirect(url_for("settings"))

    current = type("Current", (), {k: bool(existing.get(k)) for k in ENV_KEYS})
    return render_template("settings.html", current=current)


if __name__ == "__main__":
    print("Meta Ads Automation UI running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
