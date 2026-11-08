"""Comment-your-state replies (owner, Nov 8: "we need to convert those views into likes and follows").

Find Your State Reels ask people to comment their state. Anyone who does gets a reply with that state's rank and
value, read from ranks.json: the exact verified numbers the Reel showed, saved next to its video when it was built.

Rules: replies only on Find Your State Reels from the last 14 days, only to comments that name a state, one reply per
comment (tracked in state/replies.json and double-checked against the comment's existing replies), never to our own
comments, at most MAX_PER_RUN per run. Any API error is logged and skipped: this never fails a run.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .data import STATES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLIED = os.path.join(ROOT, "state", "replies.json")
PT = ZoneInfo("America/Los_Angeles")
MAX_PER_RUN = 25
WINDOW_DAYS = 14

NAMES = {name.lower(): fips for fips, (name, _) in STATES.items()}
NAMES.update({"d.c.": "11", "dc": "11", "washington dc": "11", "washington d.c.": "11", "district of columbia": "11"})
# two-letter codes that are also everyday words or other places ("ok", "me", "LA" for Los Angeles) never count alone
AMBIGUOUS = {"ok", "me", "hi", "in", "or", "oh", "id", "la"}
ABBR = {abbr.lower(): fips for fips, (_, abbr) in STATES.items() if abbr.lower() not in AMBIGUOUS}
_NAME_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in sorted(NAMES, key=len, reverse=True)) + r")(?![a-z])")

TEMPLATES = [
    "{state}: #{rank} of 51 for {what}, at {value}.{us}",
    "#{rank} of 51! {state} comes in at {value} for {what}.{us}",
    "{state} lands at #{rank} of 51: {value} ({what}).{us}",
]
TAIL = ["", " New state ranking every Wed & Sat 📊", " Which state should we rank next?"]


def states_in(text):
    """FIPS codes named in a comment, in order, at most 3. Two-letter codes count only when they're the whole comment
    ("CA", "tx 🙃"), so words like 'in', 'or', 'me', 'ok' never match."""
    low = text.lower()
    found = [NAMES[m.group(1)] for m in _NAME_RE.finditer(low)]
    if not found:
        bare = re.sub(r"[^a-z]", "", low)
        if len(bare) == 2 and bare in ABBR:
            found = [ABBR[bare]]
    out = []
    for f in found:
        if f not in out:
            out.append(f)
    return out[:3]


def reply_text(ranks, fips_list, comment_id):
    h = int(hashlib.sha256(comment_id.encode()).hexdigest(), 16)
    rows = {r["fips"]: r for r in ranks["rows"]}
    parts = []
    for i, f in enumerate(fips_list):
        r = rows.get(f)
        if not r:
            continue
        us = f" U.S.: {ranks['us']}." if ranks.get("us") and i == len(fips_list) - 1 else ""
        if parts:      # second and third states: short form, the measure was already named
            parts.append(f"{r['state']}: #{r['rank']}, {r['value']}.{us}")
            continue
        t = TEMPLATES[h % len(TEMPLATES)]
        parts.append(t.format(state=r["state"], rank=r["rank"], value=r["value"], what=ranks["what"], us=us))
    if not parts:
        return ""
    return " ".join(parts) + TAIL[(h >> 12) % len(TAIL)]


def save_ranks(out_dir, what, us, rows):
    """Written by every Find Your State builder: rows = [(fips, value_text)] in rank order (#1 first)."""
    os.makedirs(out_dir, exist_ok=True)
    data = {"what": what, "us": us,
            "rows": [{"fips": f, "state": STATES[f][0], "rank": k + 1, "value": v} for k, (f, v) in enumerate(rows)]}
    with open(os.path.join(out_dir, "ranks.json"), "w") as fh:
        json.dump(data, fh, indent=1)


def _load(path, default):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


def run(posted, log=print):
    """Reply to new state comments on recent Find Your State Reels. Returns the number of replies sent."""
    from .instagram import Instagram, InstagramError
    replied = _load(REPLIED, {})
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    targets = []
    for key, p in posted.items():
        if "find_" not in key or not p.get("media_id") or datetime.fromisoformat(p["posted_at"]) < since:
            continue
        # the Reel's media folder: media/<Pacific date of the run>_<job>, where ranks.json was saved at build time
        day = datetime.fromisoformat(p["posted_at"]).astimezone(PT).strftime("%Y-%m-%d")
        ranks = _load(os.path.join(ROOT, "media", f"{day}_{p.get('job', '')}", "ranks.json"), None)
        if ranks:
            targets.append((key, p["media_id"], ranks))
    if not targets:
        return 0
    ig = Instagram()
    me = ig.me().get("username", "").lower()
    sent = 0
    for key, media_id, ranks in targets:
        try:
            comments = ig._call("GET", f"{media_id}/comments",
                                {"fields": "id,text,username,timestamp,replies{username}", "limit": "100"}).get("data", [])
        except InstagramError as e:
            log(f"  ! comments for {key}: {e}")
            continue
        for c in comments:
            cid = c["id"]
            if sent >= MAX_PER_RUN or cid in replied or c.get("username", "").lower() == me:
                continue
            if any(r.get("username", "").lower() == me for r in (c.get("replies") or {}).get("data", [])):
                replied[cid] = {"key": key, "at": "already replied"}
                continue
            fips = states_in(c.get("text", ""))
            text = reply_text(ranks, fips, cid) if fips else ""
            if not text:
                continue
            try:
                ig._call("POST", f"{cid}/replies", {"message": text})
                replied[cid] = {"key": key, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "states": [STATES[f][1] for f in fips]}
                sent += 1
            except InstagramError as e:
                log(f"  ! reply to a comment on {key}: {e}")
                replied[cid] = {"key": key, "at": "error", "error": str(e)[:200]}   # don't retry the same one forever
    os.makedirs(os.path.dirname(REPLIED), exist_ok=True)
    with open(REPLIED, "w") as fh:
        json.dump(replied, fh, indent=1, sort_keys=True)
    return sent
