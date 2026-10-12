"""Shared post plumbing."""
import os
from dataclasses import dataclass, field

from . import checks as C
from . import questions as Q
from .render import html_to_png

DISCLAIMER = "Data: official U.S. government & Freddie Mac releases. For information only, not financial advice."
MAX_CAROUSEL = 10


class DataError(Exception):
    """Data failed checks or isn't ready; nothing is posted."""


class NoContent(DataError):
    """Nothing new to post (e.g. this month's data already covered). Skipped quietly."""


@dataclass
class Post:
    key: str
    caption: str
    images: list = field(default_factory=list)
    media: str = "feed"
    checks: C.Report = field(default_factory=C.Report)

    @property
    def size(self):
        return {"story": "story", "reel": "reel"}.get(self.media, "feed")


def with_question(text, kind, key, **values):
    q = Q.pick(kind, key, **values)
    return f"{text}\n\n{q}" if q else text
