#!/usr/bin/env python3
"""Save your Instagram token to the macOS Keychain (for insights.py). Input is hidden.

    python3 "~/Documents/Social Media Accounts/PaycheckMath/save_token.py"
"""
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

token = getpass.getpass("Paste your Instagram token, then press Enter (it stays hidden): ").strip()
if not (token.startswith("IG") and token.isalnum() and len(token) > 100):
    sys.exit("❌ That doesn't look like an Instagram token (it should start with IGAA and be one long string). "
             "Copy it again from Meta and re-run this.")
try:
    with urllib.request.urlopen(f"https://graph.instagram.com/me?fields=username&access_token={token}", timeout=30) as r:
        user = json.loads(r.read()).get("username")
except urllib.error.HTTPError as e:
    msg = json.loads(e.read() or b"{}").get("error", {}).get("message", "")
    sys.exit(f"❌ Instagram rejected this token: {msg}\nIf you clicked Generate again since copying it, copy the newest one.")
subprocess.run(["security", "add-generic-password", "-U", "-s", "paycheckmath-ig", "-a", os.environ.get("USER", "me"),
                "-w", token], check=True, capture_output=True)
stamp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "insights", ".token_refreshed")
os.makedirs(os.path.dirname(stamp), exist_ok=True)
open(stamp, "w").close()
print(f"✅ Saved. Token works for @{user}. Remember: GitHub's IG_TOKEN secret should have this same token.")
