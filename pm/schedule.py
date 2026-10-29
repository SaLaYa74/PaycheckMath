"""Paycheck Math posting calendar (US Pacific). Edit freely; no workflow change needed.
live=False means PREVIEW (built + checked, not published)."""
from dataclasses import dataclass

WINDOW_HOURS = 12
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
    # Moments, not the calendar: BLS posts CPI and the jobs report at 8:30am ET (5:30 PT). This checks every
    # morning and posts "just released" the day new numbers land (idles otherwise). Listed first so it beats
    # the monthly rotation to a brand-new month.
    Job("release",     "reel_release",  (MON, TUE, WED, THU, FRI, SAT, SUN), "06:00", live=True,
        note="Reel: just-released inflation / jobs-report numbers"),
    # Weekly: Freddie Mac publishes Thursdays at noon ET (9am PT)
    Job("mortgage",    "reel_mortgage", (THU,), "12:00", live=True, note="Reel: this week's mortgage rate"),
    # Monthly BLS data: 11 rotating formats (pay vs prices, groceries, minutes of work, gas, 7 trend lines),
    # biggest moves first. Never repeats a format for the same data month; idles until BLS publishes new data.
    # Times alternate midday/evening so the weekly report can tell us which slot performs better.
    Job("monthly_mon", "reel_monthly",  (MON,), "16:00", live=True, note="Reel: monthly rotation (7pm ET)"),
    Job("monthly_tue", "reel_monthly",  (TUE,), "12:00", live=True, note="Reel: monthly rotation"),
    Job("monthly_wed", "reel_monthly",  (WED,), "12:00", live=True, note="Reel: monthly rotation"),
    Job("monthly_fri", "reel_monthly",  (FRI,), "16:00", live=True, note="Reel: monthly rotation (7pm ET)"),
    Job("monthly_sat", "reel_monthly",  (SAT,), "09:00", live=True, note="Reel: monthly rotation"),
    Job("monthly_sun", "reel_monthly",  (SUN,), "10:00", live=True, note="Reel: monthly rotation"),
    # Pictures (Oct 28, owner asked for still images too): carousels and pictures earn saves, Reels earn reach.
    # Each slot posts the next unused picture format for the latest BLS month (cheat-sheet carousel, then the
    # grocery receipt), then idles until new data.
    Job("pics_sun",    "pic_monthly",   (SUN,), "11:00", live=True, note="Picture/carousel: monthly cheat sheet / grocery receipt"),
    Job("pics_thu",    "pic_monthly",   (THU,), "17:00", live=True, note="Picture/carousel: monthly cheat sheet / grocery receipt"),
    # Monthly share-first board: BLS state pay comes out mid-to-late month; checked every Saturday,
    # posts once per new data month (idles otherwise).
    Job("find_state",  "reel_find_state", (SAT,), "17:00", live=True, note="Reel: Find Your State (weekly pay, all 50 + DC)"),
]
