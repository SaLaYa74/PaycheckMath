#!/usr/bin/env python3
"""Paycheck Math runner: builds, checks and publishes posts on the calendar in pm/schedule.py.

    python3 autopost.py                    # run whatever is due now (what GitHub runs hourly)
    python3 autopost.py mlb_story          # run one job or builder now (dry run unless --live)
    python3 autopost.py --list             # show the calendar

Every post goes through the data-check gate (pm/checks.py). Any blocking
check means it is NOT published. Results are saved in media/<run>/checks.json.
Posting needs BOTH the job marked live in schedule.py AND the repo variable
POSTING_ENABLED=true (the global kill switch).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from PIL import Image

from pm import checks as C
from pm import core as P
from pm import reels as R
from pm.schedule import JOBS, WINDOW_HOURS, Job
from pm.voice import humanize

ROOT = os.path.dirname(os.path.abspath(__file__))
PT = ZoneInfo("America/Los_Angeles")
POSTED = os.path.join(ROOT, "posted.json")
RUNS = os.path.join(ROOT, "state", "runs.json")
DONE = ("posted", "previewed", "done", "duplicate", "skipped")


def sh(*cmd):
    return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as f:
            f.write(text + "\n")
    print(text)


def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def git_push(message, paths):
    paths = [p for p in paths if os.path.exists(os.path.join(ROOT, p))]
    if not paths:
        return sh("git", "rev-parse", "HEAD")
    sh("git", "add", *paths)
    if sh("git", "diff", "--cached", "--name-only"):
        sh("git", "commit", "-m", message)
        sh("git", "pull", "--rebase", "--autostash", "--quiet")
        sh("git", "push", "--quiet")
    return sh("git", "rev-parse", "HEAD")


def wait_public(url, tries=24, video=False):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                ctype = r.headers.get("Content-Type", "")
                if r.status == 200 and (not video or ctype.startswith("video/")):
                    return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"Media never became publicly available (or wrong content type): {url}")


def to_jpeg(png):
    jpg = png[:-4] + ".jpg"
    Image.open(png).convert("RGB").save(jpg, "JPEG", quality=90, optimize=True)  # API requires JPEG
    os.remove(png)
    return jpg


class Runner:
    def __init__(self, live_allowed, in_ci, force=False):
        self.live_allowed, self.in_ci, self.force = live_allowed, in_ci, force
        self._ctx = None
        self.touched = set()

    def build(self, job, out_dir):
        return R.BUILDERS[job.builder](out_dir, posted=load(POSTED))

    def run(self, job, now):
        """Returns (status, detail)."""
        out_dir = os.path.join(ROOT, "media", f"{now:%Y-%m-%d}_{job.name}")
        try:
            post = self.build(job, out_dir)
        except P.NoContent as e:
            return "skipped", str(e)
        except P.DataError as e:
            return "waiting", str(e)

        post.caption = humanize(post.key, post.caption)     # human opener/sign-off; data lines untouched
        posted = load(POSTED)
        if post.key in posted and not self.force:
            return "duplicate", f"{post.key} already posted"

        # Final gate: rendered images + caption, on top of the builder's data checks.
        if post.media == "reel":
            images = [post.images[0]["reel"]]          # video + cover were checked by the builder
            cover = post.images[0]["cover"]
        else:
            images = [to_jpeg(img[post.size]) for img in post.images][:P.MAX_CAROUSEL]
            cover = None
            for img in images:
                C.image(post.checks, img, post.size)
        if post.media in ("feed", "reel"):
            C.caption(post.checks, post.caption)
        post.checks.save(os.path.join(out_dir, "checks.json"))
        with open(os.path.join(out_dir, "caption.txt"), "w") as f:
            f.write(post.caption)
        self.touched.add(os.path.relpath(out_dir, ROOT))

        live = job.live and self.live_allowed
        mode = "🚀 LIVE" if live else "🧪 PREVIEW"
        summary(f"\n## {mode} · `{job.name}` → `{post.key}` ({post.media}, {len(images)} image{'s' * (len(images) > 1)})")
        summary(post.checks.markdown())
        if post.media in ("feed", "reel"):
            summary("```\n" + post.caption + "\n```")

        if not post.checks.ok:
            return "blocked", "; ".join(i["detail"] for i in post.checks.blocked)[:300]
        if not self.in_ci and not live:
            return "previewed", f"saved to {out_dir}"

        rel = [os.path.relpath(p, ROOT) for p in images]
        sha = git_push(f"{'Post' if live else 'Preview'} {post.key}", [os.path.relpath(out_dir, ROOT)])
        repo = os.environ.get("GITHUB_REPOSITORY") or "SaLaYa74/PaycheckMath"
        raw = lambda r: f"https://raw.githubusercontent.com/{repo}/{sha}/{r}"
        if post.media == "reel":
            # Videos are served through jsDelivr (proper video/mp4 type); the cover through GitHub raw.
            urls = [f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{rel[0]}"]
            cover_url = raw(os.path.relpath(cover, ROOT))
            summary(f"\n![cover]({cover_url})\n\n🎬 [Watch the Reel]({urls[0]})")
        else:
            urls = [raw(r) for r in rel]
            cover_url = None
            summary("\n" + " ".join(f"![{i + 1}]({u})" for i, u in enumerate(urls)))
        if not live:
            for u in urls + ([cover_url] if cover_url else []):
                wait_public(u, video=u.endswith(".mp4"))   # proves Instagram will be able to fetch it
            return "previewed", "built, checked and hosting verified, not published"

        from pm.instagram import Instagram
        ig = Instagram()
        limit = ig.publishing_limit()
        if limit.get("quota_usage", 0) >= limit.get("config", {}).get("quota_total", 50):
            return "waiting", "Instagram daily publishing limit reached"
        for u in urls + ([cover_url] if cover_url else []):
            wait_public(u, video=u.endswith(".mp4"))
        media_id = ig.publish(urls, post.caption, media=post.media, cover_url=cover_url, trial=job.trial)
        link = None if post.media == "story" else ig.permalink(media_id)
        posted = load(POSTED)
        posted[post.key] = {"media_id": media_id, "permalink": link, "media": post.media, "images": len(urls),
                            "trial": job.trial, "scheduled": job.time,
                            "job": job.name, "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        save(POSTED, posted)
        self.touched.add("posted.json")
        summary(f"✅ Published {post.media}: {link or post.key}")
        return "posted", link or post.key


def due_jobs(now, runs):
    out = []
    for job in JOBS:
        if now.weekday() not in job.days:
            continue
        hh, mm = map(int, job.time.split(":"))
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if not (start <= now < start + timedelta(hours=WINDOW_HOURS)):
            continue
        rec = runs.get(f"{now:%Y-%m-%d}:{job.name}", {})
        if rec.get("status") in DONE:
            continue
        final = now >= start + timedelta(hours=WINDOW_HOURS - 1)
        out.append((job, final))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default="scheduled")
    ap.add_argument("--live", action="store_true", help="allow publishing for live jobs when run locally")
    ap.add_argument("--force", action="store_true", help="ignore duplicate protection")
    ap.add_argument("--at", help="pretend it's this Pacific time, e.g. '2026-10-10 08:05' (testing)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        days = "Mon Tue Wed Thu Fri Sat Sun".split()
        for j in sorted(JOBS, key=lambda j: (j.days[0], j.time)):
            print(f"{'LIVE   ' if j.live else 'preview'}  {j.time} PT  {','.join(days[d] for d in j.days):<28} {j.name:<15} {j.note}")
        return

    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    live_allowed = args.live or (in_ci and os.environ.get("POSTING_ENABLED", "").strip().lower() == "true")
    now = datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=PT) if args.at else datetime.now(PT)
    runs = load(RUNS)

    # Names used by the original workflow file keep working.
    preview_only = args.target.startswith("preview:")
    args.target = args.target.split(":", 1)[-1]
    if args.target == "scheduled":
        todo = due_jobs(now, runs)
    else:
        match = [j for j in JOBS if j.name == args.target]
        job = match[0] if match else Job(args.target, args.target, tuple(range(7)), "00:00", live=False)
        if preview_only:
            job = Job(job.name, job.builder, job.days, job.time, live=False, note=job.note, trial=job.trial)
        todo = [(job, True)]
    if not todo:
        print(f"Nothing due at {now:%a %H:%M} PT.")
        return

    runner = Runner(live_allowed, in_ci, args.force)
    failed = []
    for job, final in todo:
        try:
            status, detail = runner.run(job, now)
        except Exception as e:
            traceback.print_exc()
            status, detail = "error", f"{type(e).__name__}: {e}"
        if status in ("waiting", "blocked") and final:
            status = "skipped" if status == "waiting" else "blocked-final"
        runs[f"{now:%Y-%m-%d}:{job.name}"] = {"status": status, "detail": detail[:300],
                                              "at": now.isoformat(timespec="minutes")}
        icon = {"posted": "✅", "previewed": "🧪", "done": "🗄️", "duplicate": "⏭️", "skipped": "⏭️",
                "waiting": "⏳", "blocked": "⛔", "blocked-final": "⛔", "error": "❌"}.get(status, "•")
        summary(f"{icon} **{job.name}**: {status}: {detail}")
        if status in ("blocked-final", "error"):
            failed.append(job.name)

    save(RUNS, runs)
    runner.touched.add("state")
    if in_ci:
        git_push(f"Run {now:%Y-%m-%d %H:%M} PT", sorted(runner.touched))
    if failed:
        summary(f"\n❌ Needs attention: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
