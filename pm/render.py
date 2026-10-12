"""Render HTML templates to PNG with headless Google Chrome."""
import os
import shutil
import subprocess
import sys
import tempfile

CHROME = os.environ.get("CHROME") or next(
    (c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 shutil.which("google-chrome"), shutil.which("google-chrome-stable"),
                 shutil.which("chromium"), shutil.which("chromium-browser")) if c and os.path.exists(c)),
    None)

SIZES = {
    "feed": (1080, 1350),    # Instagram feed 4:5
    "story": (1080, 1920),   # IG Stories / TikTok 9:16
    "reel": (1080, 1920),    # Reels: 9:16 with UI-safe padding
    "square": (1080, 1080),  # profile pic, X/Twitter, carousel covers
}


def html_to_png(html, out_path, size="feed"):
    w, h = SIZES[size]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        src = f.name
    try:
        if not CHROME:
            raise RuntimeError("Google Chrome not found (set CHROME=/path/to/chrome)")
        linux = ["--no-sandbox"] if sys.platform.startswith("linux") else []
        subprocess.run([
            CHROME, *linux, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", f"--window-size={w},{h}",
            "--virtual-time-budget=6000", "--default-background-color=00000000",
            f"--screenshot={os.path.abspath(out_path)}", "file://" + src,
        ], check=True, capture_output=True, timeout=90)
    finally:
        os.unlink(src)
    return out_path
