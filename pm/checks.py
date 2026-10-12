"""Pre-publish data checks.

Every post carries a Report. A single BLOCK result stops the post from publishing;
WARN results are published but surfaced in the run summary. The full report is
saved next to the post's images (checks.json) as an audit trail.
"""
import json
import os
import re

from PIL import Image, ImageStat

PASS, WARN, BLOCK = "pass", "warn", "block"

# Plausible ranges per sport. Anything outside is almost certainly a data error.
RANGES = {
    "nfl": {"spread": 24, "total": (28, 66)},
    "cfb": {"spread": 63, "total": (28, 95)},
    "mlb": {"total": (4.5, 15), "ml": (100, 700)},  # unused here; kept for parity with SharpCharts
    "nba": {"spread": 25, "total": (180, 265)},
}

BANNED_WORDS = ("guaranteed returns", "guaranteed return", "get rich", "risk-free", "risk free", "free money",
                "sure thing", "can't lose", "cant lose", "you should buy", "you should sell")


class Report:
    def __init__(self, subject=""):
        self.subject = subject
        self.items = []

    def add(self, status, name, detail=""):
        self.items.append({"status": status, "check": name, "detail": str(detail)})
        return status == PASS

    def require(self, ok, name, detail=""):
        """BLOCK when ok is False."""
        return self.add(PASS if ok else BLOCK, name, "" if ok else detail)

    def expect(self, ok, name, detail=""):
        """WARN when ok is False."""
        return self.add(PASS if ok else WARN, name, "" if ok else detail)

    def extend(self, other):
        self.items.extend(other.items)
        return self

    @property
    def blocked(self):
        return [i for i in self.items if i["status"] == BLOCK]

    @property
    def warnings(self):
        return [i for i in self.items if i["status"] == WARN]

    @property
    def ok(self):
        return not self.blocked

    def counts(self):
        return {s: sum(i["status"] == s for i in self.items) for s in (PASS, WARN, BLOCK)}

    def markdown(self):
        c = self.counts()
        lines = [f"**Data checks:** ✅ {c[PASS]} passed · ⚠️ {c[WARN]} warnings · ⛔ {c[BLOCK]} blocking"]
        for i in self.blocked + self.warnings:
            icon = "⛔" if i["status"] == BLOCK else "⚠️"
            lines.append(f"- {icon} {i['check']}: {i['detail']}")
        return "\n".join(lines)

    def save(self, path):
        with open(path, "w") as f:
            json.dump({"subject": self.subject, "counts": self.counts(), "checks": self.items}, f, indent=2)


# ---------------- reusable checks ----------------

def line_ranges(rep, sport, label, spread=None, total=None, moneylines=()):
    r = RANGES[sport]
    if spread is not None and "spread" in r:
        rep.require(abs(spread) <= r["spread"], f"{label}: spread in range", f"spread {spread} outside ±{r['spread']}")
    if total is not None and "total" in r:
        lo, hi = r["total"]
        rep.require(lo <= total <= hi, f"{label}: total in range", f"total {total} outside {lo}-{hi}")
    for ml in moneylines:
        if ml is None:
            continue
        lo, hi = r.get("ml", (100, 5000))
        rep.require(lo <= abs(ml) <= hi, f"{label}: moneyline in range", f"moneyline {ml} outside ±{lo}-{hi}")


def image(rep, path, size):
    expected = {"feed": (1080, 1350), "story": (1080, 1920), "reel": (1080, 1920), "square": (1080, 1080)}[size]
    name = os.path.basename(path)
    if not rep.require(os.path.exists(path), f"{name}: rendered", "file missing"):
        return
    im = Image.open(path)
    rep.require(im.size == expected, f"{name}: dimensions", f"{im.size} != {expected}")
    rep.require(os.path.getsize(path) > 30_000, f"{name}: not empty", f"only {os.path.getsize(path)} bytes")
    spread = max(ImageStat.Stat(im.convert("L")).stddev)
    rep.require(spread > 12, f"{name}: has visible content", f"image looks blank (contrast {spread:.1f})")


def caption(rep, text):
    rep.require(0 < len(text) <= 2200, "caption: length", f"{len(text)} chars (max 2200)")
    rep.require(text.count("#") <= 30, "caption: hashtag limit", f"{text.count('#')} hashtags (max 30)")
    rep.require("not financial advice" in text.lower(), "caption: not-financial-advice line", "missing disclaimer")
    rep.require("source:" in text.lower(), "caption: cites its source", "no 'Source:' line")
    low = text.lower()
    bad = [w for w in BANNED_WORDS if re.search(r"(?<![\w'])" + re.escape(w) + r"(?![\w'])", low)]
    rep.require(not bad, "caption: brand language", f"contains {bad}")
    rep.require("None" not in text and "nan" not in low.split(), "caption: no missing values", "caption contains None/nan")
