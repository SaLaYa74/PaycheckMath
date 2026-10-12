#!/usr/bin/env python3
"""Instagram performance report: which post types gain views, keep viewers, and earn follows.

    python3 insights.py            # report for the last 30 days → out/insights/<date>.md (+ .json)

Reads the access token from the macOS Keychain (service "paycheckmath-ig"), never prints it,
and refreshes it there when it's older than ~3 weeks. Reports stay on this Mac (out/ is not
committed), because reach and watch-time numbers aren't public.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "https://graph.instagram.com"
SERVICE = "paycheckmath-ig"
STAMP = os.path.join(ROOT, "out", "insights", ".token_refreshed")

METRICS = {  # requested one by one so an unsupported metric never sinks the whole report
    "FEED": ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "profile_visits", "follows"],
    "CAROUSEL_ALBUM": ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "profile_visits", "follows"],
    "REELS": ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
              "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"],
    "STORY": ["views", "reach", "replies", "shares", "follows", "profile_visits"],
}


def keychain_token():
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-w"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("No token in Keychain yet. Run:  security add-generic-password -U -s paycheckmath-ig -a \"$USER\" -w")
    return r.stdout.strip()


def save_token(token):
    subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", os.environ.get("USER", "me"),
                    "-w", token], check=True, capture_output=True)


def call(path, token, **params):
    params["access_token"] = token
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"{path.split('?')[0]} ({e.code}): {msg}") from None


def maybe_refresh(token):
    """Keep the Keychain copy alive (tokens last 60 days; refresh after ~21)."""
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    if os.path.exists(STAMP) and time.time() - os.path.getmtime(STAMP) < 21 * 86400:
        return token
    if not os.path.exists(STAMP):        # first run: start the clock, token is brand new
        open(STAMP, "w").close()
        return token
    try:
        d = call("refresh_access_token", token, grant_type="ig_refresh_token")
        save_token(d["access_token"])
        open(STAMP, "w").close()
        return d["access_token"]
    except Exception as e:
        print("  ! token refresh skipped:", e)
        return token


def job_index():
    """Map Instagram media id -> our post key/job, from posted.json (pulled from GitHub)."""
    subprocess.run(["git", "pull", "-q"], cwd=ROOT, capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    posted = json.load(open(os.path.join(ROOT, "posted.json"))) if os.path.exists(os.path.join(ROOT, "posted.json")) else {}
    return {v["media_id"]: {"key": k, **v} for k, v in posted.items()}


def kind_of(key, job):
    if not key:
        return "manual (posted by hand)"
    for part, label in (("mortgage", "Reel: mortgage"), ("pay_vs", "Reel: pay vs prices"), ("groceries", "Reel: groceries"),
                        ("minutes", "Reel: minutes of work"), ("gas", "Reel: gas")):
        if part in key:
            return label
    return job or key


def main(days=30):
    token = maybe_refresh(keychain_token())
    me = call("me", token, fields="user_id,username,followers_count,media_count")
    uid = me["user_id"]
    index = job_index()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    media, url = [], f"{uid}/media"
    params = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink", "limit": 50}
    while url:
        d = call(url, token, **params)
        media += d.get("data", [])
        nxt = d.get("paging", {}).get("next")
        if not nxt or (media and datetime.fromisoformat(media[-1]["timestamp"].replace("+0000", "+00:00")) < since):
            break
        url, params = nxt.replace(BASE + "/", "").split("?")[0], dict(urllib.parse.parse_qsl(nxt.split("?")[1]))
        params.pop("access_token", None)
    try:
        stories = call(f"{uid}/stories", token, fields="id,media_type,timestamp").get("data", [])
        for s in stories:
            s["media_product_type"] = "STORY"
        media += stories
    except RuntimeError:
        pass

    rows = []
    for m in media:
        ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts < since:
            continue
        product = m.get("media_product_type") or "FEED"
        mtype = "REELS" if product == "REELS" else "STORY" if product == "STORY" else (
            "CAROUSEL_ALBUM" if m.get("media_type") == "CAROUSEL_ALBUM" else "FEED")
        vals = {}
        for metric in METRICS[mtype]:
            try:
                d = call(f"{m['id']}/insights", token, metric=metric)
                vals[metric] = d["data"][0]["values"][0]["value"] if d.get("data") else None
            except RuntimeError:
                vals[metric] = None
        meta = index.get(m["id"], {})
        rows.append({"id": m["id"], "ts": ts.isoformat(), "when": ts.astimezone().strftime("%a %m/%d %H:%M"), "type": mtype,
                     "kind": kind_of(meta.get("key"), meta.get("job")), "permalink": m.get("permalink"), **vals})

    try:
        acct = call(f"{uid}/insights", token, metric="reach,follower_count,profile_views,accounts_engaged",
                    period="day", metric_type="total_value",
                    since=int((datetime.now(timezone.utc) - timedelta(days=min(days, 28))).timestamp()),
                    until=int(datetime.now(timezone.utc).timestamp()))
        account = {a["name"]: (a.get("total_value") or {}).get("value") for a in acct.get("data", [])}
    except RuntimeError as e:
        account = {"error": str(e)}

    # Aggregate by post kind
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in ("views", "reach", "saved", "shares", "follows", "comments", "ig_reels_avg_watch_time"):
            if isinstance(r.get(k), (int, float)):
                agg[r["kind"]][k].append(r[k])
    avg = lambda xs: sum(xs) / len(xs) if xs else None

    out_dir = os.path.join(ROOT, "out", "insights")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# @{me.get('username')} insights · last {days} days · {stamp}",
             f"Followers: **{me.get('followers_count')}** · posts: {me.get('media_count')} · account (28d): {account}", "",
             "## By post type (averages per post)", "",
             "| Type | Posts | Views | Reach | Saves | Shares | Follows | Comments | Reel avg watch (s) |",
             "|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v, d=0: "—" if v is None else f"{v:,.{d}f}"
    for kind, m in sorted(agg.items(), key=lambda kv: -(avg(kv[1]["views"]) or 0)):
        n = max(len(v) for v in m.values()) if m else 0
        watch = avg(m["ig_reels_avg_watch_time"])
        lines.append(f"| {kind} | {n} | {fmt(avg(m['views']))} | {fmt(avg(m['reach']))} | {fmt(avg(m['saved']), 1)} | "
                     f"{fmt(avg(m['shares']), 1)} | {fmt(avg(m['follows']), 1)} | {fmt(avg(m['comments']), 1)} | "
                     f"{fmt(watch / 1000 if watch else None, 1)} |")
    # Posting-time test: Reels posted midday vs. evening (Pacific)
    reels = [r for r in rows if r["type"] == "REELS" and isinstance(r.get("reach"), (int, float))]
    slot = lambda r: "Evening (4pm PT / 7pm ET)" if datetime.fromisoformat(r["ts"]).astimezone().hour >= 15 else "Midday (before 3pm PT)"
    by_slot = defaultdict(list)
    for r in reels:
        by_slot[slot(r)].append(r)
    if by_slot:
        lines += ["", "## Posting-time test (Reels)", "", "| Slot | Reels | Avg reach | Avg views | Avg watch (s) |", "|---|---|---|---|---|"]
        for k, rs in sorted(by_slot.items()):
            wt = [r["ig_reels_avg_watch_time"] for r in rs if isinstance(r.get("ig_reels_avg_watch_time"), (int, float))]
            lines.append(f"| {k} | {len(rs)} | {fmt(avg([r['reach'] for r in rs]))} | {fmt(avg([r['views'] or 0 for r in rs]))} | "
                         f"{fmt(avg(wt) / 1000 if wt else None, 1)} |")
    if reels:
        best = max(reels, key=lambda r: r["reach"])
        lines += ["", f"**Best Reel to re-post with a trending sound:** {best['kind']} ({best['when']}, reach {best['reach']}) {best.get('permalink') or ''}",
                  "Open the app → Reels → tap a trending sound → upload this Reel's video (in the GitHub media folder) with that sound."]
    lines += ["", "## Every post", "", "| When | Kind | Views | Reach | Saves | Shares | Follows | Avg watch (s) |",
              "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["ts"], reverse=True):
        w = r.get("ig_reels_avg_watch_time")
        lines.append(f"| {r['when']} | {r['kind']} | {fmt(r.get('views'))} | {fmt(r.get('reach'))} | {fmt(r.get('saved'))} | "
                     f"{fmt(r.get('shares'))} | {fmt(r.get('follows'))} | {fmt(w / 1000 if w else None, 1)} |")
    report = "\n".join(lines)
    with open(os.path.join(out_dir, f"{stamp}.md"), "w") as f:
        f.write(report)
    with open(os.path.join(out_dir, f"{stamp}.json"), "w") as f:
        json.dump({"account": me | {"insights": account}, "posts": rows}, f, indent=2, default=str)
    print(report)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
