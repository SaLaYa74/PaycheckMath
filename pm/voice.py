"""Caption voice: lead with the data, one call to action, nothing that reads like an ad.

The data lines are never edited here. We drop the "👉 Follow" line and add a single save/share
line, picked deterministically from the post key so re-runs produce the same caption.
"""
import hashlib

# Save/share prompt on every post: saves and shares are what push a post to non-followers.
SAVE_SHARE = {
    "home": ["📌 Save this if you're house hunting. 📤 Send it to someone who's buying.",
             "📤 Send this to a friend shopping for a home. 📌 Save it to compare next week."],
    "money": ["📤 Send this to the person who does the grocery run. 📌 Save it for your budget.",
              "📌 Save this for your next budget check. 📤 Share it with someone who'd be surprised.",
              "📤 Send this to a friend who says \"everything costs more.\" 📌 Save it for later."],
}


def humanize(key, caption):
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    lines = [l for l in caption.split("\n") if not l.startswith("👉")]   # Instagram already shows Follow
    # save/share line goes right before the source block
    cut = next((i for i, l in enumerate(lines) if l.startswith(("Source:", "Data:"))), len(lines))
    body = lines[:cut]
    while body and not body[-1].strip():
        body.pop()
    if "save this" not in caption.lower() and "📤" not in caption:   # keep a builder's own share line
        bank = SAVE_SHARE["home" if "mortgage" in key.lower() else "money"]
        body += ["", bank[(h >> 16) % len(bank)]]
    return "\n".join(body + [""] + lines[cut:]).replace("\n\n\n", "\n\n")
