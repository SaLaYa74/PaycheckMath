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
APPROVED = {            # story keys the owner approved in chat. Nothing else posts.
    "story-rentpay-2025",  # owner: "Approve it" (Nov 22, 2026), after seeing the preview
}
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


def _line_svg(pts, scene, p):
    """A line over time that draws itself as p goes 0 -> 1; marks: [(year, text, color)] dots + labels once drawn."""
    W_, H_, L_, R_, T_, B_ = 960, 700, 110, 40, 60, 70
    lo, hi = scene["yrange"]
    x0, x1 = pts[0][0], pts[-1][0]
    X = lambda yr: L_ + (yr - x0) / (x1 - x0) * (W_ - L_ - R_)
    Y = lambda v: T_ + (hi - v) / (hi - lo) * (H_ - T_ - B_)
    k = p * (len(pts) - 1)
    i = int(k)
    drawn = [(X(yr), Y(v)) for yr, v in pts[:i + 1]]
    if i < len(pts) - 1:
        (ya, va), (yb, vb) = pts[i], pts[i + 1]
        f = k - i
        drawn.append((X(ya + (yb - ya) * f), Y(va + (vb - va) * f)))
    g = []
    for t in scene["yticks"]:
        g.append(f'<line x1="{L_}" y1="{Y(t):.1f}" x2="{W_ - R_}" y2="{Y(t):.1f}" stroke="#E5E7EB" stroke-width="3"/>'
                 f'<text x="{L_ - 16}" y="{Y(t) + 11:.1f}" text-anchor="end" font-size="32" font-weight="800" fill="#6B7280">{t:g}</text>')
    for yr in scene["xticks"]:
        g.append(f'<text x="{X(yr):.1f}" y="{H_ - 18}" text-anchor="middle" font-size="32" font-weight="800" fill="#6B7280">{yr}</text>')
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in drawn)
    g.append(f'<path d="{path}" fill="none" stroke="#1F2937" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>')
    for yr, text, col in scene.get("marks", ()):
        idx = next(j for j, (y_, _) in enumerate(pts) if y_ == yr)
        if idx <= k + 1e-9:
            v = pts[idx][1]
            g.append(f'<circle cx="{X(yr):.1f}" cy="{Y(v):.1f}" r="17" fill="{col}" stroke="#fff" stroke-width="5"/>'
                     f'<text x="{X(yr):.1f}" y="{Y(v) - 32:.1f}" text-anchor="middle" font-family="Baloo 2" font-size="54" '
                     f'font-weight="800" fill="{col}" stroke="#FFFDF7" stroke-width="8" paint-order="stroke">{escape(text)}</text>')
    return f'<svg viewBox="0 0 {W_} {H_}" style="width:100%" font-family="Nunito, Arial, sans-serif">{"".join(g)}</svg>'


def frame(scene, lt, dur, ctx):
    """HTML for one moment: scene dict, lt = seconds into the scene's line, dur = the line's length."""
    hl = scene.get("hl_color", "#EF4444")
    title = escape(scene["head"]).replace("{hl}", f"<em>{escape(scene.get('hl', ''))}</em>").replace("\n", "<br>")
    fs = min(96, int(1700 / max(len(x) for x in scene["head"].replace("{hl}", scene.get("hl", "")).split("\n"))))
    kind = scene["kind"]
    if kind == "versus":
        # two bars racing up: heights proportional to the real growth, numbers counting with them
        q = _ease(min(1.0, 0.35 + lt / 0.8))
        (va, la, ca), (vb, lb, cb) = [t[:3] for t in scene["pair"]]
        fmt = scene.get("fmt") or (lambda v: f"+{v:.0f}%")
        top = max(va, vb)
        bar = lambda val, lab, col: (
            f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%">'
            f'<div class="big" style="--hl:{col};font-size:150px;margin-bottom:10px">{fmt(val * q)}</div>'
            f'<div style="width:78%;height:{70 * val / top * q:.1f}%;background:{col};border-radius:28px 28px 8px 8px;'
            f'box-shadow:inset 0 -16px 0 rgba(0,0,0,.10)"></div>'
            f'<div class="bigl" style="font-size:50px;margin-top:14px">{escape(lab)}</div></div>')
        mid = (f'<div style="display:flex;gap:40px;height:820px;align-items:flex-end;border-bottom:6px solid #1F2937;'
               f'padding:0 20px">{bar(va, la, ca)}{bar(vb, lb, cb)}</div>')
    elif kind == "line":
        mid = _line_svg(ctx["series"], scene, min(1.0, lt / max(dur * 0.85, 0.1)) if scene.get("draw") else 1.0)
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
            if s["kind"] in ("number", "versus") and s.get("count", True):
                t_c = 0.0 if s is scenes[0] else start           # the hook counts from frame 1
                times.update(snap(t_c + j / FPS) for j in range(int(1.0 * FPS)))
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
            if i == 0:
                start = 0.0                                       # the hook animates from frame 1
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

_PROF = {}


def _profile_var(year, group, needles):
    """The data-profile estimate whose label contains every needle (profile codes shift between years: the median
    home value is DP04_0088E in 2007 and DP04_0089E in 2025)."""
    import json as _json
    if (year, group) not in _PROF:
        _PROF[(year, group)] = _json.loads(D._plain_get(
            f"https://api.census.gov/data/{year}/acs/acs1/profile/groups/{group}.json"))["variables"]
    hits = [k for k, d in _PROF[(year, group)].items() if k.endswith("E") and not k.endswith("PE")
            and all(n in d["label"] for n in needles)]
    if len(hits) != 1:
        raise DataError(f"ACS {year} {group}: {len(hits)} profile matches for {needles}")
    return hits[0]


PROFILE = {"B25064_001E": ("DP04", ("GROSS RENT", "Occupied units paying rent", "Median (dollars)")),
           "B19013_001E": ("DP03", ("Total households", "Median household income (dollars)")),
           "B25077_001E": ("DP04", ("VALUE", "Owner-occupied units", "Median (dollars)"))}


def _year_checked(rep, var, year, states=True):
    """({fips: value} or {}, U.S. value) for one ACS year; the detailed table must match the data profile for every
    state and for the U.S."""
    group, needles = PROFILE[var]
    prof = _profile_var(year, group, needles)
    us, us_p = D._acs(year, var, "us:1").get("1"), D._acs(year, prof, "us:1", profile=True).get("1")
    rep.require(us is not None and us == us_p, f"ACS {year} {var}: U.S. detailed = profile", f"{us} vs {us_p}")
    vals = {}
    if states:
        vals = {f: v for f, v in D._acs(year, var, "state:*").items() if f in D.STATES}
        same = D._acs(year, prof, "state:*", profile=True)
        bad = [D.STATES[f][1] for f, v in vals.items() if same.get(f) != v]
        rep.require(len(vals) == 51 and not bad, f"ACS {year} {var}: 51 states, detailed = profile",
                    f"{len(vals)}; differ {bad[:5]}")
    return vals, us


def _rentpay(out_dir, key, base=2019):
    """Since 2019, rent outran paychecks in nearly every state; the twist is where it didn't. Tested Nov 20: U.S. rent
    +42%, income +29%; 47 of 51 states rent faster; Hawaii (priciest homes) one of 4 where pay kept up."""
    rep = C.Report("story rent vs pay")
    year = D.acs_year()
    if year is None:
        raise DataError("Census ACS data unreachable")
    r1, ur1 = _year_checked(rep, "B25064_001E", year)
    r0, ur0 = _year_checked(rep, "B25064_001E", base)
    i1, ui1 = _year_checked(rep, "B19013_001E", year)
    i0, ui0 = _year_checked(rep, "B19013_001E", base)
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


def _whole(v):
    from decimal import Decimal, ROUND_HALF_UP
    return int(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _bubble(out_dir, key):
    """Homes are less affordable now than at the 2007 bubble peak: years of household income for the typical home.
    Tested Nov 22: 2007 3.8, low 2013 3.3, 2025 4.4 (record 4.42 in 2024)."""
    rep = C.Report("story bubble")
    year = D.acs_year()
    if year is None:
        raise DataError("Census ACS data unreachable")
    years = [y for y in range(2005, year + 1) if y != 2020]          # no standard 2020 1-year release
    series = []
    for y in years:
        h, i = D._acs(y, "B25077_001E", "us:1").get("1"), D._acs(y, "B19013_001E", "us:1").get("1")
        rep.require(h and i and 2.5 <= h / i <= 7, f"ACS {y}: U.S. years of income plausible", f"{h} / {i}")
        series.append((y, h / i))
    for y in (2007, 2013, year):                                      # the years the narrator names: profile check
        _, h = _year_checked(rep, "B25077_001E", y, states=False)
        _, i = _year_checked(rep, "B19013_001E", y, states=False)
    if not rep.ok:
        raise DataError("bubble data failed checks: " + "; ".join(i["detail"] for i in rep.blocked))
    r = dict(series)
    one = lambda v: f"{v:.1f}"
    peak07 = max((v, y) for y, v in series if 2005 <= y <= 2008)
    low = min((v, y) for y, v in series if y >= 2009)
    if not (round(r[year], 1) > round(peak07[0], 1) and peak07[1] == 2007 and low[1] == 2013):
        raise NoContent("The data no longer says 'worse than 2007'; drop this story.")
    steps = [(a, b) for (a, _), (b, _) in zip(series, series[1:]) if a >= 2013]
    rises = sum(1 for a, b in steps if r[b] > r[a])
    rep.require(rises >= len(steps) - 2, "story: 'less affordable almost every year since 2013' holds",
                f"rose in {rises} of {len(steps)} releases")
    rep2 = C.Report("states")
    y_, home, us_home = D.acs_states(rep2, "home")
    y2, inc, us_inc = D.acs_states(rep2, "income")
    rep.extend(rep2)
    if not rep.ok or y_ != year or y2 != year:
        raise DataError("state data failed checks")
    yrs = {f: home[f] / inc[f] for f in D.STATES}
    rows = sorted(yrs.items(), key=lambda kv: -kv[1])
    top, tv = rows[0]
    st = lambda f: D.STATES[f][0]
    ctx = {"series": series, "ranks": {f: k + 1 for k, (f, _) in enumerate(rows)},
           "labels": {f: f"{v:.1f}" for f, v in yrs.items()}, "bins": _bins(rows, lambda v: f"{v:.1f}"),
           "top": [(st(f), f"{v:.1f} yrs") for f, v in rows[:3]], "low": [(st(f), f"{v:.1f} yrs") for f, v in rows[::-1][:3]],
           "source": f"Census ACS 2005–{year}"}
    line = dict(yrange=(2.8, 4.8), yticks=(3.0, 3.5, 4.0, 4.5), xticks=(2005, 2010, 2015, 2020, year))
    scenes = [
        {"kind": "versus", "head": "Worse Than the\n{hl}?", "hl": "2007 Bubble", "hl_color": "#DC2626",
         "sub": "Years of household income to buy the typical U.S. home", "fmt": lambda v: f"{v:.1f}",
         "pair": ((r[2007], "2007 bubble", "#F97316"), (r[year], "Today", "#DC2626")),
         "line": "Remember the 2007 housing bubble? Homes are less affordable right now."},
        {"kind": "line", "draw": True, **line, "head": "Years of Pay to Buy\nthe Typical {hl}", "hl": "Home",
         "marks": [(2007, one(r[2007]), "#F97316"), (year, one(r[year]), "#DC2626")],
         "line": f"At the 2007 peak, the typical home cost {one(r[2007])} years of income. Today it's {one(r[year])}."},
        {"kind": "line", **line, "head": "The Low Point: {hl}", "hl": "2013", "hl_color": "#16A34A",
         "marks": [(2007, one(r[2007]), "#F97316"), (2013, one(r[2013]), "#16A34A"), (year, one(r[year]), "#DC2626")],
         "line": f"In 2013, it was just {one(r[2013])}. Since then, homes have gotten less affordable almost every year."},
        {"kind": "map", "head": "Worst: {hl}", "hl": st(top), "outline": (top,), "pill": f"{tv:.1f} years of pay",
         "pill_bg": "#DC2626", "line": f"In {st(top)}, the typical home now costs {tv:.1f} years of income."},
        {"kind": "cta", "head": "Bubble or the\n{hl}?", "hl": "New Normal", "hl_color": "#3B82F6", "lists": "both",
         "line": "Bubble, or the new normal? Tell us what you think, and your state."},
    ]
    allowed = {one(v) for _, v in series} | {f"{v:.1f}" for v in yrs.values()} | {"2007", "2013"}
    check_script(rep, scenes, allowed, words=(40, 85))
    save_ranks(out_dir, "years of income to buy the typical home", f"{us_home / us_inc:.1f} yrs", [(f, f"{v:.1f} yrs") for f, v in rows])
    mp4, cover, secs, prov = build_video(out_dir, key, scenes, ctx, key)
    hist = " → ".join(f"{y}: {r[y]:.1f}" for y in (2005, 2007, 2013, 2019, year))
    caption = (f"Homes are less affordable now than at the peak of the 2007 housing bubble. 🏠📈\n\n"
               f"Years of household income it takes to buy the typical U.S. home:\n{hist}\n\n"
               f"Worst states: " + ", ".join(f"{st(f)} {v:.1f}" for f, v in rows[:3])
               + f". Most affordable: " + ", ".join(f"{st(f)} {v:.1f}" for f, v in rows[::-1][:3]) + ".\n\n"
               "💬 Bubble, or the new normal? Tell us what you think, and your state 👇\n📤 Send this to someone "
               "waiting for prices to crash.\n🔁 Follow for a new state ranking every Monday, Wednesday and Saturday."
               f"\n\nSource: U.S. Census Bureau, American Community Survey 1-year estimates 2005–{year} (no 2020 "
               "release): median value of owner-occupied homes (owners' estimates) ÷ median household income. "
               f"Detailed and data-profile tables match for the years named.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n"
               f"#housingmarket {TAGS}")
    return finish(rep, key, mp4, cover, secs, prov, caption)


def _homevalue(out_dir, key, base=2019):
    """Since 2019, home values jumped 50%+ in most states; the twist is where they barely moved. Tested Nov 22:
    U.S. +$130,600 (+54%); 34 states +50%; Maine +85%; D.C. +11%."""
    rep = C.Report("story home values")
    year = D.acs_year()
    if year is None:
        raise DataError("Census ACS data unreachable")
    h1, us1 = _year_checked(rep, "B25077_001E", year)
    h0, us0 = _year_checked(rep, "B25077_001E", base)
    if not rep.ok:
        raise DataError("home value data failed checks: " + "; ".join(i["detail"] for i in rep.blocked))
    g = {f: _whole((h1[f] / h0[f] - 1) * 100) for f in D.STATES}
    for f in D.STATES:
        rep.require(-10 <= g[f] <= 120, f"{D.STATES[f][1]}: growth plausible", f"{g[f]}%")
    gain = us1 - us0
    usd = lambda v: f"${v:,.0f}"
    n50 = sum(1 for v in g.values() if v >= 50)
    rows = sorted(D.STATES, key=lambda f: (-g[f], f))
    (s1, s2, s3), low = rows[:3], rows[-1]
    pricey = sorted(D.STATES, key=lambda f: -h1[f]).index(low) + 1          # rank of the twist state by home value
    if n50 < 20 or gain <= 0:
        raise NoContent("The data no longer tells this story; drop it.")
    st = lambda f: D.STATES[f][0]
    def col(f):
        v = g[f]
        return (("#7F1D1D", "#fff") if v >= 70 else ("#DC2626", "#fff") if v >= 60 else ("#F97316", "#1F2937")
                if v >= 50 else ("#FDBA74", "#1F2937") if v >= 35 else ("#FEF3C7", "#1F2937"))
    ctx = {"ranks": {f: k + 1 for k, f in enumerate(rows)}, "labels": {f: f"+{g[f]}%" for f in D.STATES},
           "bins": [(c, "#fff", "", "") for c in ("#7F1D1D", "#DC2626", "#F97316", "#FDBA74", "#FEF3C7")],
           "colors": {f: col(f) for f in D.STATES},
           "legend": [("#7F1D1D", "", "70%+", ""), ("#DC2626", "", "60–70%", ""), ("#F97316", "", "50–60%", ""),
                      ("#FDBA74", "", "35–50%", ""), ("#FEF3C7", "", "under 35%", "")],
           "source": f"Census ACS {base} & {year}"}
    twist = (f"The twist? {st(low)}, one of the priciest places in America, rose just {g[low]}%." if pricey <= 5 else
             f"The twist? {st(low)} rose just {g[low]}%.")
    scenes = [
        {"kind": "number", "head": "Your Home Since {hl}", "hl": str(base), "hl_color": "#16A34A", "value": gain,
         "fmt": lambda v: "+" + usd(v), "label": "typical U.S. home value gain",
         "line": f"In just {year - base} years, the typical American home gained {usd(gain)} in value."},
        {"kind": "fill", "head": "Up 50% or More in\n{hl} States", "hl": str(n50),
         "line": f"Home values rose 50% or more in {n50} states."},
        {"kind": "map", "head": "Leader: {hl}", "hl": st(s1), "outline": (s1, s2, s3), "pill": f"{st(s1)} +{g[s1]}%",
         "pill_bg": "#7F1D1D", "line": f"{st(s1)} leads, up {g[s1]}%. {st(s2)} and {st(s3)} aren't far behind."},
        {"kind": "map", "head": "The Twist: {hl}", "hl": st(low), "hl_color": "#3B82F6", "outline": (low,),
         "pill": f"{st(low)} +{g[low]}%", "pill_bg": "#3B82F6", "line": twist},
        {"kind": "cta", "head": "Winning or\n{hl}?", "hl": "Priced Out", "hl_color": "#DC2626",
         "line": "Great if you own. Brutal if you're trying to buy. Which side are you on? Tell us your state."},
    ]
    allowed = {f"{v}%" for v in g.values()} | {usd(gain), "50%", str(n50), str(base), str(year - base)}
    check_script(rep, scenes, allowed, words=(40, 85))
    save_ranks(out_dir, f"how much home values rose since {base}", f"+{_whole((us1 / us0 - 1) * 100)}%",
               [(f, f"+{g[f]}%") for f in rows])
    mp4, cover, secs, prov = build_video(out_dir, key, scenes, ctx, key)
    caption = (f"Since {base}, the typical American home gained {usd(gain)} in value (+{_whole((us1 / us0 - 1) * 100)}%). "
               f"In {n50} states, home values rose 50% or more. 🏡💸\n\nBiggest jumps:\n"
               + "\n".join(f"{k + 1}. {st(f)}: +{g[f]}%" for k, f in enumerate(rows[:5]))
               + "\n\nSmallest: " + ", ".join(f"{st(f)} +{g[f]}%" for f in rows[::-1][:3]) + ".\n\n"
               "💬 Winning or priced out? Tell us your state 👇\n📤 Send this to a friend who's house hunting.\n🔁 "
               "Follow for a new state ranking every Monday, Wednesday and Saturday."
               f"\n\nSource: U.S. Census Bureau, American Community Survey 1-year estimates, {base} and {year}: median "
               "value of owner-occupied homes (owners' estimates), each year's own dollars. Detailed and data-profile "
               f"tables match for every state.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#realestate {TAGS}")
    return finish(rep, key, mp4, cover, secs, prov, caption)


# Hand-picked, in order. Each is (key, builder). A story posts only after the owner approves it (APPROVED).
STORIES = [
    ("story-rentpay-2025", _rentpay),
    ("story-bubble-2025", _bubble),          # Nov 22: owner asked for these two as previews ("Yes, build both")
    ("story-homevalue-2025", _homevalue),
]


def _previewed(key):
    return bool(glob.glob(os.path.join(ROOT, "media", "*", f"{key}.mp4")))


def reel_voice(out_dir, posted=None, previews_only=False):
    """Posts the next approved story (max one a week), else builds a preview of the next unapproved one.
    previews_only: just build the next missing preview (never touches approved stories)."""
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
            if previews_only:
                continue
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
