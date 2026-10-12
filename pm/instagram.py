"""Minimal Instagram API (Instagram Login) client for publishing images and carousels.

The access token is read from the IG_TOKEN environment variable and is never
printed or written to disk by this module.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.instagram.com"


class InstagramError(Exception):
    pass


class Instagram:
    def __init__(self, token=None):
        self.token = token or os.environ.get("IG_TOKEN", "").strip()
        if not self.token:
            raise InstagramError("IG_TOKEN is not set.")
        self._user_id = None

    def _call(self, method, path, params=None):
        params = dict(params or {})
        params["access_token"] = self.token
        body = urllib.parse.urlencode(params).encode()
        if method == "GET":
            req = urllib.request.Request(f"{BASE}/{path}?{body.decode()}")
        else:
            req = urllib.request.Request(f"{BASE}/{path}", data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            # Error bodies contain Meta's message, never the token.
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            raise InstagramError(f"{method} /{path.split('?')[0]} failed ({e.code}): {msg}") from None

    def me(self):
        return self._call("GET", "me", {"fields": "user_id,username"})

    @property
    def user_id(self):
        if self._user_id is None:
            self._user_id = self.me()["user_id"]
        return self._user_id

    def publishing_limit(self):
        d = self._call("GET", f"{self.user_id}/content_publishing_limit", {"fields": "quota_usage,config"})
        return (d.get("data") or [{}])[0]

    def _wait_ready(self, container_id, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            status = self._call("GET", container_id, {"fields": "status_code"}).get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Media container {container_id} status {status}")
            time.sleep(5)
        raise InstagramError(f"Media container {container_id} not ready after {timeout}s")

    def publish(self, image_urls, caption, media="feed", cover_url=None, trial=False):
        """Publish one image, a 2-10 image carousel, a Story, or a Reel (image_urls=[video_url]).
        Returns the new media id."""
        if not 1 <= len(image_urls) <= 10:
            raise InstagramError(f"Need 1-10 images, got {len(image_urls)}")
        if media == "reel":
            params = {"media_type": "REELS", "video_url": image_urls[0], "caption": caption, "share_to_feed": "true"}
            if cover_url:
                params["cover_url"] = cover_url
            if trial:
                # Trial Reel: shown to non-followers first; Instagram shares it to followers if it performs.
                params["trial_params"] = json.dumps({"graduation_strategy": "SS_PERFORMANCE"})
            try:
                cid = self._call("POST", f"{self.user_id}/media", params)["id"]
            except InstagramError as e:
                if not trial:
                    raise
                print(f"  ! Trial Reels not available via API ({e}); posting as a normal Reel")
                params.pop("trial_params")
                cid = self._call("POST", f"{self.user_id}/media", params)["id"]
            self._wait_ready(cid, timeout=900)   # video processing takes longer
            return self._call("POST", f"{self.user_id}/media_publish", {"creation_id": cid})["id"]
        if media == "story":
            if len(image_urls) != 1:
                raise InstagramError("A Story is one image")
            cid = self._call("POST", f"{self.user_id}/media",
                             {"image_url": image_urls[0], "media_type": "STORIES"})["id"]
        elif len(image_urls) == 1:
            cid = self._call("POST", f"{self.user_id}/media",
                             {"image_url": image_urls[0], "caption": caption})["id"]
        else:
            children = []
            for url in image_urls:
                child = self._call("POST", f"{self.user_id}/media",
                                   {"image_url": url, "is_carousel_item": "true"})["id"]
                self._wait_ready(child)
                children.append(child)
            cid = self._call("POST", f"{self.user_id}/media",
                             {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})["id"]
        self._wait_ready(cid)
        return self._call("POST", f"{self.user_id}/media_publish", {"creation_id": cid})["id"]

    def permalink(self, media_id):
        return self._call("GET", media_id, {"fields": "permalink"}).get("permalink")


def refresh_token(token):
    """Exchange a long-lived token (>=24h old) for a fresh 60-day one."""
    q = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": token})
    try:
        with urllib.request.urlopen(f"{BASE}/refresh_access_token?{q}", timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise InstagramError(f"Token refresh failed ({e.code})") from None
    return d["access_token"], int(d.get("expires_in", 0))
