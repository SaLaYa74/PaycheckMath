"""Paycheck Math Reels engine: chart animates from frame 1 under a hook, holds, loops. Original beat."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

from .music import make_beat
from .render import html_to_png

FPS = 30


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
    except ImportError:
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"], check=True)
        import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ease(x):
    return 1 - (1 - x) ** 3  # ease-out cubic


def make_reel(out_dir, name, hook, chart_html, tag, seed, hold=5.2):
    """Motion from frame 1: the chart animates in under the hook headline, holds so it can be read,
    and ends on the full chart (loops cleanly back to the empty chart). chart_html(p) -> HTML.
    `hook` and `tag` are baked into chart_html by the caller. Returns (mp4, cover_jpg)."""
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="reel_")
    seq = []  # (png, seconds)
    steps = 24
    for i in range(steps):                                   # 1.6s build-in, starting at t=0
        path = os.path.join(work, f"{i:03d}.png")
        html_to_png(chart_html(_ease(i / (steps - 1))), path, "reel")
        seq.append((path, 0.067))
    last_chart = seq[-1][0]
    seq.append((last_chart, hold))                           # hold long enough to read
    total = sum(s for _, s in seq)
    audio = os.path.join(work, "beat.wav")
    make_beat(audio, total + 0.2, seed)
    listing = os.path.join(work, "frames.txt")
    with open(listing, "w") as f:
        for path, secs in seq:
            f.write(f"file '{path}'\nduration {secs:.3f}\n")
        f.write(f"file '{seq[-1][0]}'\n")  # concat demuxer needs the last file repeated
    mp4 = os.path.join(out_dir, f"{name}.mp4")
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-i", audio, "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-profile:v", "high", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-shortest", "-movflags", "+faststart", mp4], check=True)
    cover = os.path.join(out_dir, f"{name}_cover.jpg")
    Image.open(last_chart).convert("RGB").save(cover, "JPEG", quality=90)
    shutil.rmtree(work, ignore_errors=True)
    return mp4, cover


def video_checks(rep, mp4):
    """Instagram Reels requirements + sanity: 9:16 1080x1920, 3-90s, has audio, < 20MB (CDN limit)."""
    name = os.path.basename(mp4)
    if not rep.require(os.path.exists(mp4), f"{name}: rendered", "video missing"):
        return
    size_mb = os.path.getsize(mp4) / 1e6
    rep.require(0.2 < size_mb < 20, f"{name}: file size", f"{size_mb:.1f} MB")
    info = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", mp4], capture_output=True, text=True).stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    secs = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else 0
    rep.require(3 <= secs <= 90, f"{name}: duration", f"{secs:.1f}s (needs 3-90s)")
    rep.require("1080x1920" in info, f"{name}: 1080x1920", "wrong resolution")
    rep.require("Audio: aac" in info, f"{name}: has audio", "no AAC audio track")
    rep.require("Video: h264" in info, f"{name}: H.264 video", "wrong codec")


