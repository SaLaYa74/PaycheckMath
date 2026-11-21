"""Voiced 30-second explainers (owner, Nov 20: "videos with animations and voiceovers... 30-second videos... pretty
much fully automated"). PILOT: preview-only until the owner approves (pm/schedule.py voice_tue).

verified data -> script lines -> voice per line (pm/tts.py) -> scenes timed to each line -> word-by-word captions
-> quiet music under the voice -> checks -> Reel.

Checks on top of the data's own: every number spoken must be one of the verified values (formatted exactly as shown),
20-45 seconds long, and a studio voice (ElevenLabs/OpenAI). The macOS draft voice can build previews, never posts.
The caption says it's an AI voiceover (Meta asks for realistic AI audio to be disclosed).
"""
import os
import re
import shutil
import subprocess
import tempfile
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

# Owner, Nov 20: "don't push any of these videos using the voiceover just yet. Send me samples and previews first and
# get them approved first." autopost.py refuses to publish a voiced video while this is False, whatever the job says.
# Flip it ONLY after the owner explicitly approves a sample in chat.
OWNER_APPROVED = False

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
    if kind == "number":
        q = _ease(min(1.0, 0.35 + lt / 0.7)) if scene.get("count", True) else 1.0
        mid = (f'<div class="big" style="--hl:{hl}">{escape(scene["fmt"](scene["value"] * q))}</div>'
               f'<div class="bigl">{escape(scene["label"])}</div>'
               + L.map_svg(ctx["ranks"], ctx["labels"], ctx["bins"], 0.0, outline=scene.get("show", ()),
                           show=scene.get("show", ()), small_list=False))
    else:
        p = min(1.0, lt / max(dur * 0.9, 0.1)) if kind == "fill" else 1.0
        mid = (L.map_svg(ctx["ranks"], ctx["labels"], ctx["bins"], p, outline=scene.get("outline", ())) + _legend(ctx["bins"])
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
                        "[v][mm]amix=inputs=2:duration=first:normalize=0[a]",
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


def check_script(rep, scenes, allowed):
    """Every number the narrator says must be one of the verified values, formatted exactly as computed."""
    said = [m.group(0).rstrip(",.") for s in scenes for m in NUM.finditer(s["line"])]
    bad = [x for x in said if x not in allowed]
    rep.require(not bad, "script: every spoken number comes from the verified data", f"not in the data: {bad}")
    words = sum(len(s["line"].split()) for s in scenes)
    rep.require(55 <= words <= 110, "script: about 30 seconds of words", f"{words} words")


def finish(rep, key, mp4, cover, secs, prov, caption):
    from .reels import _post
    rep.require(20 <= secs <= 45, "voiced: 20-45 seconds", f"{secs:.1f}s")
    rep.require(prov in V.STUDIO, "voiced: studio voice (ElevenLabs/OpenAI/Kokoro), not the draft voice",
                f"voice provider is {prov!r}: add ELEVENLABS_API_KEY (or OPENAI_API_KEY) as a GitHub secret")
    if prov in V.STUDIO:
        caption = caption.replace("\n\nSource:", "\n🎙️ AI voiceover\n\nSource:", 1)
    return _post(key, mp4, cover, caption, rep)


# ---------------------------------------------------------------- editions

def _home(out_dir, posted):
    """Salary to afford the typical home (the 29K-view board, Nov 11), narrated. Same math and checks as
    reels._find_home: median home value, 20% down, 30-year fixed at Freddie Mac's weekly rate, P&I = 28% of pay."""
    rep = C.Report("voice home")
    year = D.acs_year()
    if year is None:
        raise DataError("Census ACS data unreachable")
    key = f"acs{year}-voice-home"
    if key in (posted or {}):
        raise NoContent(f"{key} already posted")
    y, home, us_home = D.acs_states(rep, "home")
    D.check_series(rep, ["MORTGAGE30"])
    if not home or not rep.ok:
        raise DataError("home data failed checks: " + "; ".join(i["detail"] for i in rep.blocked))
    rate_day, rate = D.series("MORTGAGE30")[-1]
    r = rate / 1200
    pay = lambda price: price * 0.80 * r / (1 - (1 + r) ** -360)
    r6 = 0.06 / 12
    rep.require(abs(200_000 * r6 / (1 - (1 + r6) ** -360) - 1199.10) < 0.01, "mortgage formula self-check", "formula off")
    sal = {f: pay(v) * 12 / 0.28 for f, v in home.items()}
    us = pay(us_home) * 12 / 0.28
    rows = sorted(sal.items(), key=lambda kv: -kv[1])
    st = lambda f: D.STATES[f][0]
    full = lambda v: f"${round(v, -3):,.0f}"
    short = lambda v: f"${v / 1e3:,.0f}K"
    (f1, v1), (f2, _), (f3, _), (fl, vl) = rows[0], rows[1], rows[2], rows[-1]
    ctx = {"ranks": {f: k + 1 for k, (f, _) in enumerate(rows)}, "labels": {f: short(v) for f, v in sal.items()},
           "bins": _bins(rows, short), "top": [(st(f), full(v)) for f, v in rows[:3]],
           "low": [(st(f), full(v)) for f, v in rows[::-1][:3]], "source": f"Census ACS {year} · Freddie Mac"}
    rate_s = f"{rate:.2f}%"
    scenes = [
        {"kind": "number", "head": "To Afford a Home\nin {hl}", "hl": st(f1), "value": v1, "fmt": full,
         "label": "a year, before taxes", "show": (f1,),
         "line": f"To afford the typical home in {st(f1)}, you'd need to earn {full(v1)} a year."},
        {"kind": "number", "head": "Across the {hl}", "hl": "U.S.", "value": us, "fmt": full, "hl_color": "#3B82F6",
         "label": f"with 20% down at {rate_s}",
         "line": f"Across the U.S., it takes {full(us)}, with 20% down at today's {rate_s} mortgage rate."},
        {"kind": "fill", "head": "The Salary to Afford\na Home, by {hl}", "hl": "State",
         "line": "Here's what it takes in every state. The darker the red, the bigger the paycheck you need."},
        {"kind": "map", "head": "The Salary to Afford\na Home, by {hl}", "hl": "State", "outline": (f1, f2, f3),
         "lists": "top", "line": f"{st(f1)}, {st(f2)} and {st(f3)} need the most."},
        {"kind": "map", "head": "The Salary to Afford\na Home, by {hl}", "hl": "State", "outline": (fl,), "lists": "both",
         "line": f"The easiest? {st(fl)}, where {full(vl)} a year gets you there."},
        {"kind": "cta", "head": "Find Your {hl}", "hl": "State", "hl_color": "#3B82F6", "lists": "both",
         "line": "Where does your state land? Comment it below, and follow for a new state ranking every week."},
    ]
    check_script(rep, scenes, {full(v) for v in sal.values()} | {full(us), rate_s, "20%"})
    save_ranks(out_dir, "the salary to afford the typical home", short(us), [(f, short(v)) for f, v in rows])
    mp4, cover, secs, prov = build_video(out_dir, "voice_home", scenes, ctx, f"voice-home-{year}")
    medal = ["🥇", "🥈", "🥉", "4.", "5."]
    caption = (f"What you'd need to earn to afford the typical home, in every state 🏡\n\n"
               + "\n".join(f"{medal[k]} {st(f)}: {full(v)}/year" for k, (f, v) in enumerate(rows[:5]))
               + f"\n...\n51. {st(fl)}: {full(vl)}/year\n\nU.S.: {full(us)}/year.\n\n"
               "💬 Comment your state: higher or lower than you expected?\n📤 Send this to the friend who says they'll "
               "buy next year.\n🔁 A new state ranking every Monday, Wednesday and Saturday."
               f"\n\nSource: U.S. Census Bureau, American Community Survey {year} 1-year (median home value); 20% down; "
               f"30-year fixed at {rate_s} (Freddie Mac, {rate_day:%b} {rate_day.day}); principal + interest = 28% of "
               f"gross pay (taxes and insurance add more).\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#homebuying {TAGS}")
    return finish(rep, key, mp4, cover, secs, prov, caption)


EDITIONS = [_home]


def reel_voice(out_dir, posted=None):
    if V.provider() is None:      # GitHub's Linux runner has no draft voice: skip quietly until a key is added
        raise NoContent("No voice yet: add ELEVENLABS_API_KEY (or OPENAI_API_KEY) as a GitHub secret.")
    for edition in EDITIONS:
        try:
            post = edition(out_dir, posted)
        except NoContent:
            continue
        except DataError:
            raise
        except Exception as e:      # voice engine trouble (install, model download, audio): wait and retry, never fail
            raise DataError(f"voice engine: {type(e).__name__}: {e}") from e
        if V.provider() == "kokoro":     # pilot: the same line in three voices, saved next to the preview
            try:
                V.voice_options("Here's what it takes to afford a home in every state. Where does yours land?",
                                os.path.join(out_dir, "voice_options.mp3"))
            except Exception as e:      # a nice-to-have; never blocks the preview
                print(f"  ! voice options: {e}")
        return post
    raise NoContent("Every voiced edition is posted.")
