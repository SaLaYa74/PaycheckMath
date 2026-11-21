"""Voiced short stories (owner, Nov 20: "videos with animations and voiceovers... fully automated"; then: "be very
selective... a good hook... a good story... not too long... a payoff... something interesting and controversial...
spark conversation... retain viewers and turn them into follows").

THE STORY RULES (every voiced video):
  1. Hook in the first 2 seconds: a surprising, true claim or a sharp question. Never a fact everyone already knows.
  2. Turn: the reveal (usually the map) that makes it bigger than the hook.
  3. Twist / payoff: the counterintuitive part ("the most expensive state is where pay kept up").
  4. A question that starts arguments, and a reason to follow.
  5. About 20-28 seconds. Every spoken number is a verified value (check_script). A story must be TRUE in the data
     before it's written: test it first, and if the data doesn't support the angle, drop the angle.
  6. At most one voiced post a week, hand-picked (STORIES), and each one approved by the owner first.

APPROVAL: autopost.py publishes a voiced video only if its key is in APPROVED. Until then a story builds as a preview
(saved to GitHub, never posted), which gets sent to the owner. Add a key ONLY after the owner approves that video in chat.

Pipeline: verified data -> script lines -> voice per line (pm/tts.py) -> scenes timed to each line -> word-by-word
captions -> quiet music under the voice, leveled to Reels loudness -> checks -> Reel. The caption says it's an AI voiceover.
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from html import escape

from PIL import Image

from . import checks as C
from . import data as D
from . import light as L
from .comments import save_ranks
from .core import DISCLAIMER, DataError, NoContent
from .music import make_beat
from .video import FPS, _render_all, ffmpeg_exe
from . import tts as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVED = set()        # story keys the owner approved in chat, e.g. {"story-rentpay-2025"}. Nothing else posts.
MIN_DAYS_BETWEEN = 6    # at most one voiced post a week

HOT = [("#7F1D1D", "#fff"), ("#DC2626", "#fff"), ("#F97316", "#1F2937"), ("#FDBA74", "#1F2937"), ("#FEF3C7", "#1F2937")]
NAMES = ("#1–10", "#11–20", "#21–30", "#31–40", "#41–51")
TAGS = "#personalfinance #costofliving #money"

VCSS = """<style>
.vh{font-family:"Baloo 2";font-weight:800;line-height:.98;text-align:center;letter-spacing:-1px}
.vh em{font-style:normal;color:var(--hl)}
.vsub{font-size:32px;font-weight:700;color:#6B7280;text-align:center;margin-top:12px}
.vmid{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0}
.big{font-family:"Baloo 2";font-weight:800;font-size:200px;line-height:1;text-align:center;color:var(--hl)}
.bigl{font-size:40px;font-weight:800;text-align:center;color:#1F2937;margin-top:6px}
.legend{display:flex;gap:10px;justify-content:center;margin-top:6px}
.lg{flex:1;display:flex;flex-direction:column;align-items:center;font-weight:800;line-height:1.05;min-width:0}
.lg i{display:block;width:100%;height:18px;border-radius:6px;margin-bottom:5px}
.lg b{font-size:21px}.lg small{font-size:19px;color:#6B7280;white-space:nowrap}
.lists{display:flex;gap:16px;margin-top:16px}
.ls{flex:1;background:#fff;border-radius:18px;padding:10px 18px;box-shadow:0 3px 0 rgba(0,0,0,.06)}
.lh{font-family:"Baloo 2";font-weight:800;font-size:26px;line-height:1.1}
.lr{display:flex;justify-content:space-between;font-weight:800;font-size:26px;line-height:1.35}
.cap{background:rgba(17,24,39,.94);border-radius:26px;padding:20px 30px;font-weight:800;font-size:50px;line-height:1.22;
     color:rgba(255,255,255,.38);text-align:center;margin-top:18px;min-height:200px;display:flex;align-items:center;
     justify-content:center}
.cap span{display:inline}.cap .wsaid{color:#fff}.cap .wnow{color:#FDE047}
.cta{align-self:center;margin-top:18px;background:#1F2937;color:#fff;font-family:"Baloo 2";font-weight:800;font-size:46px;
     padding:10px 36px;border-radius:999px}
</style>"""


def _ease(x):
    return 1 - (1 - x) ** 3


def _words(text, frac):
    """Caption HTML: words already spoken white, the current word yellow, the rest dim. Timing within a line is
    proportional to characters (the voice gives each line's exact start and length)."""
    words = text.split()
    total = sum(len(w) + 1 for w in words)
    out, acc = [], 0
    for w in words:
        start, acc = acc / total, acc + len(w) + 1
        cls = "wsaid" if acc / total <= frac else ("wnow" if start <= frac else "")   # not "s": that's the subtitle style
        out.append(f'<span class="{cls}">{escape(w)}</span>')
    return " ".join(out)


def _bins(rows, short):
    groups = [rows[0:10], rows[10:20], rows[20:30], rows[30:40], rows[40:51]]
    return [(HOT[k][0], HOT[k][1], NAMES[k], f"{short(g[-1][1])}–{short(g[0][1])}") for k, g in enumerate(groups)]


def _legend(bins):
    return '<div class="legend">' + "".join(
        f'<div class="lg"><i style="background:{b[0]}"></i><b>{escape(b[2])}</b><small>{escape(b[3])}</small></div>'
        for b in bins) + "</div>"


def _lists(top, low, color):
    col = lambda head, rows, c: (f'<div class="ls"><div class="lh" style="color:{c}">{escape(head)}</div>' + "".join(
        f'<div class="lr"><span>{escape(n)}</span><b>{escape(v)}</b></div>' for n, v in rows) + "</div>")
    return f'<div class="lists">{col("Highest", top, color)}{col("Lowest", low, "#6B7280") if low else ""}</div>'


def frame(scene, lt, dur, ctx):
    """HTML for one moment: scene dict, lt = seconds into the scene's line, dur = the line's length."""
    hl = scene.get("hl_color", "#EF4444")
    title = escape(scene["head"]).replace("{hl}", f"<em>{escape(scene.get('hl', ''))}</em>").replace("\n", "<br>")
    fs = min(96, int(1700 / max(len(x) for x in scene["head"].replace("{hl}", scene.get("hl", "")).split("\n"))))
    kind = scene["kind"]
    if kind == "versus":
        # two bars racing up: heights proportional to the real growth, numbers counting with them
        q = _ease(min(1.0, 0.35 + lt / 0.8))
        (va, la, ca), (vb, lb, cb) = scene["pair"]
        top = max(va, vb)
        bar = lambda val, lab, col: (
            f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%">'
            f'<div class="big" style="--hl:{col};font-size:150px;margin-bottom:10px">+{val * q:.0f}%</div>'
            f'<div style="width:78%;height:{70 * val / top * q:.1f}%;background:{col};border-radius:28px 28px 8px 8px;'
            f'box-shadow:inset 0 -16px 0 rgba(0,0,0,.10)"></div>'
            f'<div class="bigl" style="font-size:50px;margin-top:14px">{escape(lab)}</div></div>')
        mid = (f'<div style="display:flex;gap:40px;height:820px;align-items:flex-end;border-bottom:6px solid #1F2937;'
               f'padding:0 20px">{bar(va, la, ca)}{bar(vb, lb, cb)}</div>')
    elif kind == "number":
        q = _ease(min(1.0, 0.35 + lt / 0.7)) if scene.get("count", True) else 1.0
        mid = (f'<div class="big" style="--hl:{hl}">{escape(scene["fmt"](scene["value"] * q))}</div>'
               f'<div class="bigl">{escape(scene["label"])}</div>'
               + L.map_svg(ctx["ranks"], ctx["labels"], ctx["bins"], 0.0, outline=scene.get("show", ()),
                           show=scene.get("show", ()), small_list=False))
    else:
        p = min(1.0, lt / max(dur * 0.9, 0.1)) if kind == "fill" else 1.0
        pill = (f'<div style="align-self:center;margin-top:14px;background:{scene.get("pill_bg", "#1F2937")};color:#fff;'
                f'font-family:\'Baloo 2\';font-weight:800;font-size:44px;padding:6px 30px;border-radius:999px">'
                f'{escape(scene["pill"])}</div>') if scene.get("pill") else ""
        mid = (L.map_svg(ctx["ranks"], ctx["labels"], ctx["bins"], p, outline=scene.get("outline", ()),
                         colors=ctx.get("colors")) + _legend(ctx.get("legend") or ctx["bins"]) + pill
               + (_lists(ctx["top"], ctx["low"] if scene.get("lists") == "both" else None, ctx["bins"][0][0])
                  if scene.get("lists") else "")
               + ('<div class="cta">Comment your state 👇</div>' if kind == "cta" else ""))
    cap = f'<div class="cap"><div>{_words(scene["line"], lt / max(dur, 0.1))}</div></div>'
    body = (f'{VCSS}<div class="vh" style="--hl:{hl};font-size:{fs}px">{title}</div>'
            f'<div class="vsub">{escape(scene.get("sub", ""))}</div><div class="vmid">{mid}</div>{cap}')
    return L._page(body, True, ctx["source"])


def build_video(out_dir, name, scenes, ctx, seed):
    """Narrate, time, render and mix. Returns (mp4, cover, seconds, provider)."""
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="voiced_")
    try:
        voice, spans, total, prov = V.narrate([s["line"] for s in scenes], os.path.join(work, "voice"))
        # moments that need a fresh frame: scene starts, count-ups, the map filling, every word boundary
        snap = lambda t: round(t * FPS) / FPS
        times = {0.0}
        for (start, dur), s in zip(spans, scenes):
            t0 = 0.0 if s is scenes[0] else start
            times.add(snap(t0))
            if s["kind"] == "number" and s.get("count", True):
                times.update(snap(start + j / FPS) for j in range(int(0.7 * FPS)))
            if s["kind"] == "fill":
                times.update(snap(start + j / 15) for j in range(int(dur * 15) + 1))
            words = s["line"].split()
            tot, acc = sum(len(w) + 1 for w in words), 0
            for w in words:
                times.add(snap(start + dur * acc / tot))
                acc += len(w) + 1
            times.add(snap(start + dur))
        times = sorted(t for t in times if t < total)

        def state(t):
            i = max(k for k, (start, _) in enumerate(spans) if k == 0 or start <= t)
            start, dur = spans[i]
            return scenes[i], max(0.0, t - start), dur
        pngs = _render_all([frame(*state(t), ctx) for t in times], work)
        listing = os.path.join(work, "frames.txt")
        with open(listing, "w") as f:
            for k, path in enumerate(pngs):
                f.write(f"file '{path}'\nduration {((times[k + 1] if k + 1 < len(times) else total) - times[k]):.4f}\n")
            f.write(f"file '{pngs[-1]}'\n")
        music = os.path.join(work, "music.wav")
        make_beat(music, total + 0.5, seed)
        mp4 = os.path.join(out_dir, f"{name}.mp4")
        subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                        "-i", voice, "-i", music, "-filter_complex",
                        f"[2:a]volume=0.10,afade=t=out:st={max(0, total - 1.2):.2f}:d=1.2[m];"
                        "[1:a]aformat=channel_layouts=stereo[v];[m]aformat=channel_layouts=stereo[mm];"
                        # Nov 20: level to Reels loudness (the first Kokoro build averaged -29 dB, too quiet)
                        "[v][mm]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                        "-map", "0:v", "-map", "[a]", "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "16", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "44100", "-t", f"{total:.2f}", "-movflags", "+faststart", mp4], check=True)
        cover = os.path.join(out_dir, f"{name}_cover.jpg")
        # cover = the hook once its number has finished counting (never a mid-count number)
        k = next((i for i, t in enumerate(times) if t >= 1.0), len(pngs) - 1)
        Image.open(pngs[k]).convert("RGB").save(cover, "JPEG", quality=95, subsampling=0)
        return mp4, cover, total, prov
    finally:
        shutil.rmtree(work, ignore_errors=True)


NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def check_script(rep, scenes, allowed, words=(55, 110)):
    """Every number the narrator says must be one of the verified values, formatted exactly as computed."""
    said = [m.group(0).rstrip(",.") for s in scenes for m in NUM.finditer(s["line"])]
    bad = [x for x in said if x not in allowed]
    rep.require(not bad, "script: every spoken number comes from the verified data", f"not in the data: {bad}")
    n = sum(len(s["line"].split()) for s in scenes)
    rep.require(words[0] <= n <= words[1], "script: short (about 20-30 seconds of words)", f"{n} words")


def finish(rep, key, mp4, cover, secs, prov, caption):
    from .reels import _post
    rep.require(15 <= secs <= 40, "voiced: 15-40 seconds", f"{secs:.1f}s")
    rep.require(prov in V.STUDIO, "voiced: studio voice (ElevenLabs/OpenAI/Kokoro), not the draft voice",
                f"voice provider is {prov!r}: add ELEVENLABS_API_KEY (or OPENAI_API_KEY) as a GitHub secret")
    rep.expect(key in APPROVED, "voiced: owner approved this video", "not approved yet: builds as a preview only")
    if prov in V.STUDIO:
        caption = caption.replace("\n\nSource:", "\n🎙️ AI voiceover\n\nSource:", 1)
    return _post(key, mp4, cover, caption, rep)


# ---------------------------------------------------------------- stories

def _year_checked(rep, var, prof, year, label_must):
    """{fips: value} for one ACS year, the detailed table matching the data-profile table for every state."""
    import json as _json
    vals = {f: v for f, v in D._acs(year, var, "state:*").items() if f in D.STATES}
    lab = _json.loads(D._plain_get(D.VARS.format(year, "/profile", prof))).get("label", "")
    rep.require(label_must in lab, f"ACS {year} profile {prof} is '{label_must}'", f"label is '{lab}'")
    same = D._acs(year, prof, "state:*", profile=True)
    bad = [D.STATES[f][1] for f, v in vals.items() if same.get(f) != v]
    rep.require(len(vals) == 51 and not bad, f"ACS {year} {var}: 51 states, detailed = profile", f"{len(vals)}; differ {bad[:5]}")
    return vals, D._acs(year, var, "us:1").get("1")


def _rentpay(out_dir, key, base=2019):
    """Since 2019, rent outran paychecks in nearly every state; the twist is where it didn't. Tested Nov 20: U.S. rent
    +42%, income +29%; 47 of 51 states rent faster; Hawaii (priciest homes) one of 4 where pay kept up."""
    rep = C.Report("story rent vs pay")
    year = D.acs_year()
    if year is None:
        raise DataError("Census ACS data unreachable")
    r1, ur1 = _year_checked(rep, "B25064_001E", "DP04_0134E", year, "GROSS RENT!!Occupied units paying rent!!Median")
    r0, ur0 = _year_checked(rep, "B25064_001E", "DP04_0134E", base, "GROSS RENT!!Occupied units paying rent!!Median")
    i1, ui1 = _year_checked(rep, "B19013_001E", "DP03_0062E", year, "Median household income")
    i0, ui0 = _year_checked(rep, "B19013_001E", "DP03_0062E", base, "Median household income")
    if not rep.ok:
        raise DataError("rent/income data failed checks: " + "; ".join(i["detail"] for i in rep.blocked))
    from decimal import Decimal, ROUND_HALF_UP
    whole = lambda v: int(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    pct = lambda a, b: (a / b - 1) * 100
    # Judged at the precision shown (whole percents): a state showing "rent +28%, pay +28%" counts as pay keeping up.
    rg = {f: whole(pct(r1[f], r0[f])) for f in D.STATES}
    ig = {f: whole(pct(i1[f], i0[f])) for f in D.STATES}
    for f in D.STATES:
        rep.require(-5 <= rg[f] <= 90 and -5 <= ig[f] <= 80, f"{D.STATES[f][1]}: growth plausible", f"rent {rg[f]}, pay {ig[f]}")
    gap = {f: rg[f] - ig[f] for f in D.STATES}
    urg, uig = whole(pct(ur1, ur0)), whole(pct(ui1, ui0))
    outran = [f for f in D.STATES if gap[f] > 0]
    kept = sorted((f for f in D.STATES if gap[f] <= 0), key=lambda f: gap[f])
    if urg <= uig or len(outran) < 30 or not kept:
        raise NoContent("The data no longer tells this story (rent didn't clearly outrun pay); drop it.")
    worst = max(D.STATES, key=lambda f: (gap[f], f))
    twist = kept[0]                                                  # where pay beat rent by the most
    home = D._acs(year, "B25077_001E", "state:*")
    priciest = max(D.STATES, key=lambda f: home[f])
    st = lambda f: D.STATES[f][0]
    pc = lambda v: f"{v}%"
    order = sorted(D.STATES, key=lambda f: -gap[f])
    def col(f):
        g = gap[f]
        return (("#7F1D1D", "#fff") if g > 20 else ("#DC2626", "#fff") if g > 15 else ("#F97316", "#1F2937") if g > 10
                else ("#FDBA74", "#1F2937") if g > 0 else ("#16A34A", "#fff"))
    ctx = {"ranks": {f: k + 1 for k, f in enumerate(order)}, "labels": {f: "" for f in D.STATES},
           "bins": [(c, "#fff", "", "") for c in ("#7F1D1D", "#DC2626", "#F97316", "#FDBA74", "#16A34A")],
           "colors": {f: col(f) for f in D.STATES},
           "legend": [("#7F1D1D", "", "20+ pts", "rent way ahead"), ("#DC2626", "", "15–20", ""),
                      ("#F97316", "", "10–15", ""), ("#FDBA74", "", "0–10", ""), ("#16A34A", "", "Pay kept up", "")],
           "source": f"Census ACS {base} & {year}"}
    twist_extra = ", home of America's priciest houses," if twist == priciest else ""
    scenes = [
        {"kind": "versus", "head": "Rent vs. {hl}", "hl": "Paychecks", "hl_color": "#16A34A",
         "sub": f"Change since {base} · typical U.S. rent and household income",
         "pair": ((urg, "Rent", "#DC2626"), (uig, "Paychecks", "#16A34A")),
         "line": f"Since {base}, rent in America is up {pc(urg)}. Paychecks? Only {pc(uig)}."},
        {"kind": "fill", "head": "Rent Outran Pay in\n{hl} States", "hl": str(len(outran)),
         "line": f"Rent outran pay in {len(outran)} states."},
        {"kind": "map", "head": "Worst: {hl}", "hl": st(worst), "outline": (worst,),
         "pill": f"Rent +{pc(rg[worst])} · Pay +{pc(ig[worst])}", "pill_bg": "#DC2626",
         "line": f"In {st(worst)}, rent jumped {pc(rg[worst])} while pay rose just {pc(ig[worst])}."},
        {"kind": "map", "head": "The Surprise: {hl}", "hl": st(twist), "hl_color": "#16A34A", "outline": (twist,),
         "pill": f"Rent +{pc(rg[twist])} · Pay +{pc(ig[twist])}", "pill_bg": "#16A34A",
         "line": f"The surprise? {st(twist)}{twist_extra} is one of only {len(kept)} states where paychecks kept up."},
        {"kind": "cta", "head": "Did Your Raise\nKeep {hl}?", "hl": "Up", "hl_color": "#16A34A",
         "line": "Did your raise keep up with your rent? Tell us your state, and follow for more."},
    ]
    allowed = {pc(v) for v in list(rg.values()) + list(ig.values()) + [urg, uig]} | {str(base), str(len(outran)), str(len(kept))}
    check_script(rep, scenes, allowed, words=(40, 85))
    save_ranks(out_dir, f"how much faster rent grew than pay since {base} (points)", f"{urg - uig} pts",
               [(f, f"rent +{pc(rg[f])}, pay +{pc(ig[f])}") for f in order])
    mp4, cover, secs, prov = build_video(out_dir, key, scenes, ctx, key)
    top5 = "\n".join(f"{k + 1}. {st(f)}: rent +{pc(rg[f])}, pay +{pc(ig[f])}" for k, f in enumerate(order[:5]))
    caption = (f"Since {base}, typical rent in America is up {pc(urg)}. Typical household income: up {pc(uig)}. 😬\n\n"
               f"Rent outran pay in {len(outran)} of 50 states + D.C. Where rent pulled furthest ahead:\n{top5}\n\n"
               f"Where paychecks kept up: {', '.join(f'{st(f)} (rent +{pc(rg[f])}, pay +{pc(ig[f])})' for f in kept)}.\n\n"
               "💬 Did your raise keep up with your rent? Tell us your state 👇\n📤 Send this to your landlord. (Kidding. "
               "Mostly.)\n🔁 Follow for a new state ranking every Monday, Wednesday and Saturday."
               f"\n\nSource: U.S. Census Bureau, American Community Survey 1-year estimates, {base} and {year}: median "
               "gross rent and median household income, each year's own dollars (not adjusted for inflation). Detailed "
               f"and data-profile tables match for every state.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#rent {TAGS}")
    return finish(rep, key, mp4, cover, secs, prov, caption)


# Hand-picked, in order. Each is (key, builder). A story posts only after the owner approves it (APPROVED).
STORIES = [
    ("story-rentpay-2025", _rentpay),
]


def _previewed(key):
    return bool(glob.glob(os.path.join(ROOT, "media", "*", f"{key}.mp4")))


def reel_voice(out_dir, posted=None):
    posted = posted or {}
    if V.provider() is None:      # no voice engine here: skip quietly
        raise NoContent("No voice engine available.")
    now = datetime.now(timezone.utc)
    recent = [v for k, v in posted.items() if k.startswith("story-") and v.get("posted_at")
              and now - datetime.fromisoformat(v["posted_at"]) < timedelta(days=MIN_DAYS_BETWEEN)]
    for key, builder in STORIES:
        if key in posted:
            continue
        if key in APPROVED:
            if recent:
                raise NoContent("A voiced story posted in the last 6 days; at most one a week.")
        elif _previewed(key):
            continue               # preview built, waiting on the owner
        try:
            return builder(out_dir, key)
        except (DataError, NoContent):
            raise
        except Exception as e:     # voice engine trouble (install, model download, audio): wait and retry, never fail
            raise DataError(f"voice engine: {type(e).__name__}: {e}") from e
    raise NoContent("No voiced story to build: every one is posted or waiting for the owner's approval.")
