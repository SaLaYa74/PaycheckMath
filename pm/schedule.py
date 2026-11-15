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
    # Nov 14 (owner + Claude, 14-day numbers): Find Your State boards reach 13-16K people each (~28K views, 10-16 saves);
    # every other Reel ~17-88 people, pictures ~7. So: Find Your State three times a week, the monthly BLS rotation
    # trimmed from 6 slots to 2 (still never repeats a format per data month), pictures retired.
    Job("monthly_tue", "reel_monthly",  (TUE,), "12:00", live=True, note="Reel: monthly rotation"),
    Job("monthly_fri", "reel_monthly",  (FRI,), "16:00", live=True, note="Reel: monthly rotation (7pm ET)"),
    # Find Your State: new BLS state pay month first, otherwise the next Census edition (pm/reels.py EDITIONS).
    Job("find_state_mon", "reel_find_state", (MON,), "17:00", live=True, note="Reel: Find Your State (BLS pay month, else next Census edition)"),
    Job("find_state_wed", "reel_find_state", (WED,), "17:00", live=True, note="Reel: Find Your State (BLS pay month, else next Census edition)"),
    Job("find_state",  "reel_find_state", (SAT,), "17:00", live=True, note="Reel: Find Your State (BLS pay month, else next Census edition)"),
]
# Retired Nov 14: pics_tue / pics_thu / pics_sun (pictures reached ~7 people each) and monthly_mon / wed / sat / sun.
# Builders still exist (pm/pictures.py, reel_monthly) if we want them back.
