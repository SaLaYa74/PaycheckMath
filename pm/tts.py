"""Text-to-speech for the voiced explainers (owner, Nov 20: "videos with animations and voiceovers... fully automated").

Providers, first available wins:
  elevenlabs  ELEVENLABS_API_KEY (GitHub secret, or Mac Keychain item 'paycheckmath-elevenlabs'); voice from
              ELEVENLABS_VOICE_ID (any voice in your ElevenLabs library), default below.
  openai      OPENAI_API_KEY; voice from OPENAI_TTS_VOICE, model from OPENAI_TTS_MODEL.
  kokoro      Kokoro-82M, open source (Apache 2.0), runs on the machine itself: no account, key or cost.
              Official sources only (verified Nov 20): model hexgrad/Kokoro-82M on Hugging Face, package `kokoro`
              0.9.4 on PyPI by hexgrad (github.com/hexgrad/kokoro), PyTorch from download.pytorch.org. Installed on
              GitHub's runner only when a voiced video is being built. Voice from KOKORO_VOICE (default af_heart,
              the only A-grade voice in the official VOICES.md). Fake "Kokoro" websites exist: never use them.
  say         macOS's built-in voice. DRAFTS ONLY: the builders refuse to publish with it.
Each script line is spoken separately (ElevenLabs gets the neighbouring lines as context so the read flows), which
gives the exact start and length of every line: the animation is timed to it. Keys are never printed or logged.
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import wave

from .video import ffmpeg_exe

RATE = 44100
ELEVEN_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"     # a premade narrator voice; set ELEVENLABS_VOICE_ID to change it
ELEVEN_MODEL = "eleven_multilingual_v2"
STUDIO = ("elevenlabs", "openai", "kokoro")
KOKORO_REPO = "hexgrad/Kokoro-82M"           # the official model repo; nothing else
KOKORO_PKG = "kokoro==0.9.4"                 # verified: PyPI author hexgrad <hello@hexgrad.com>
KOKORO_DEFAULT_VOICE = "af_heart"


def _secret(env, keychain):
    v = os.environ.get(env, "").strip()
    if v or not shutil.which("security"):
        return v
    try:
        return subprocess.run(["security", "find-generic-password", "-s", keychain, "-w"], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def provider():
    if _secret("ELEVENLABS_API_KEY", "paycheckmath-elevenlabs"):
        return "elevenlabs"
    if _secret("OPENAI_API_KEY", "paycheckmath-openai"):
        return "openai"
    if os.environ.get("GITHUB_ACTIONS") == "true" or _kokoro_installed():
        return "kokoro"
    if shutil.which("say"):
        return "say"
    return None


def _kokoro_installed():
    try:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
        return True
    except ImportError:
        return False


_PIPE = {}


def _kokoro_pipe():
    """The Kokoro pipeline (American English), installing it on GitHub's runner the first time it's needed."""
    if "p" not in _PIPE:
        if not _kokoro_installed():
            if os.environ.get("GITHUB_ACTIONS") != "true":
                raise RuntimeError("Kokoro isn't installed on this machine (needs Python 3.10-3.12)")
            pip = [sys.executable, "-m", "pip", "install", "--quiet"]
            subprocess.run(pip + ["torch", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
            subprocess.run(pip + [KOKORO_PKG, "soundfile"], check=True)
            import importlib
            importlib.invalidate_caches()        # let this already-running Python see the just-installed packages
        from kokoro import KPipeline
        _PIPE["p"] = KPipeline(lang_code="a", repo_id=KOKORO_REPO)
    return _PIPE["p"]


def _kokoro(text, path, voice=None):
    pipe = _kokoro_pipe()                # installs Kokoro (and numpy/soundfile) first on the GitHub runner
    import numpy as np
    import soundfile as sf
    voice = voice or os.environ.get("KOKORO_VOICE", "").strip() or KOKORO_DEFAULT_VOICE
    chunks = []
    for r in pipe(text, voice=voice, speed=1.05):
        audio = r.audio if hasattr(r, "audio") else r[2]          # Result object (0.9.x) or (gs, ps, audio)
        if audio is not None:
            chunks.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    sf.write(path, np.concatenate(chunks), 24000)
    return path


def voice_options(text, out_path, voices=("af_heart", "af_bella", "am_michael")):
    """One audio file with the same line read by each voice (owner picks by ear). Kokoro only."""
    import tempfile
    work = tempfile.mkdtemp(prefix="voices_")
    parts = []
    for v in voices:
        wav = _kokoro(text, os.path.join(work, f"{v}.wav"), voice=v)
        parts += [wav, None]
    listing = os.path.join(work, "list.txt")
    silence = os.path.join(work, "gap.wav")
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", "0.8", silence], check=True)
    with open(listing, "w") as f:
        for p in parts:
            f.write(f"file '{p or silence}'\n")
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-c:a", "libmp3lame", "-b:a", "128k", out_path], check=True)
    return out_path


def _post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _to_wav(src, dst):
    """Any audio file -> 44.1 kHz mono 16-bit WAV (one format, so the lines can be joined sample-exact)."""
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", str(RATE),
                    "-sample_fmt", "s16", dst], check=True)
    with wave.open(dst) as w:
        return w.getnframes() / w.getframerate()


def _speak(prov, text, prev, nxt, raw):
    if prov == "elevenlabs":
        voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or ELEVEN_DEFAULT_VOICE
        audio = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                      {"xi-api-key": _secret("ELEVENLABS_API_KEY", "paycheckmath-elevenlabs"), "Accept": "audio/mpeg"},
                      {"text": text, "model_id": ELEVEN_MODEL, "previous_text": prev, "next_text": nxt,
                       "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25}})
        path = raw + ".mp3"
    elif prov == "openai":
        audio = _post("https://api.openai.com/v1/audio/speech",
                      {"Authorization": "Bearer " + _secret("OPENAI_API_KEY", "paycheckmath-openai")},
                      {"model": os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                       "voice": os.environ.get("OPENAI_TTS_VOICE", "alloy"), "input": text, "response_format": "wav",
                       "instructions": "Upbeat, confident social-media explainer narrator. Clear, quick, friendly."})
        path = raw + ".wav"
    elif prov == "kokoro":
        return _kokoro(text, raw + ".wav")
    elif prov == "say":
        path = raw + ".aiff"
        subprocess.run(["say", "-v", os.environ.get("SAY_VOICE", "Samantha"), "-r", "200", "-o", path, text], check=True)
        return path
    else:
        raise RuntimeError("no text-to-speech provider")
    with open(path, "wb") as f:
        f.write(audio)
    return path


def narrate(lines, work, prov=None, gap=0.22):
    """Speak each line; return (voice.wav, [(start_s, dur_s)] per line, total_s, provider)."""
    prov = prov or provider()
    os.makedirs(work, exist_ok=True)
    wavs, spans, t = [], [], 0.35                     # a beat of music before the first word
    for i, text in enumerate(lines):
        raw = os.path.join(work, f"line{i:02d}")
        src = _speak(prov, text, " ".join(lines[max(0, i - 2):i]), " ".join(lines[i + 1:i + 3]), raw)
        dur = _to_wav(src, raw + "_n.wav")
        wavs.append(raw + "_n.wav")
        spans.append((t, dur))
        t += dur + gap
    total = t + 0.6
    out = os.path.join(work, "voice.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        pos = 0
        for path, (start, dur) in zip(wavs, spans):
            lead = int(start * RATE) - pos
            w.writeframes(b"\x00\x00" * max(0, lead))
            with wave.open(path) as src:
                frames = src.readframes(src.getnframes())
            w.writeframes(frames)
            pos = int(start * RATE) + len(frames) // 2
        w.writeframes(b"\x00\x00" * max(0, int(total * RATE) - pos))
    return out, spans, total, prov
