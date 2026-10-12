"""Paycheck Math posting calendar (US Pacific). Edit freely; no workflow change needed.
live=False means PREVIEW (built + checked, not published)."""
from dataclasses import dataclass

WINDOW_HOURS = 6
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


@dataclass(frozen=True)
class Job:
    name: str
    builder: str
    days: tuple
    time: str
    live: bool = False
    note: str = ""
    trial: bool = False


JOBS = [
    # Freddie Mac publishes Thursdays at noon ET (9am PT)
    Job("mortgage",    "reel_mortgage", (THU,), "12:00", live=True, note="Reel: this week's mortgage rate"),
    # Monthly BLS data, rotating formats (pay vs prices, groceries, minutes of work, gas); skips when all used
    Job("monthly_mon", "reel_monthly",  (MON,), "16:00", live=True, note="Reel: monthly prices rotation"),
    Job("monthly_wed", "reel_monthly",  (WED,), "12:00", live=True, note="Reel: monthly prices rotation"),
    Job("monthly_sat", "reel_monthly",  (SAT,), "09:00", live=True, note="Reel: monthly prices rotation"),
]
