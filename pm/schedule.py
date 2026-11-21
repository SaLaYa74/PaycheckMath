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
    # Nov 20 (owner: "maps of the US... color coded"): the Thursday mortgage-rate Reel (~120 views) is replaced by a
    # US map Reel at the evening slot that works (5pm PT / 8pm ET). Housing measures, pm/reels.py MAP_EDITIONS.
    # Nov 20 PILOT (owner: "videos with animations and voiceovers... fully automated"): a 30-second narrated
    # explainer (pm/voiced.py). PREVIEW ONLY until the owner approves; skips until a voice key is added.
    Job("voice_tue",   "reel_voice",    (TUE,), "17:00", live=False, note="Reel PILOT: 30s voiced explainer (preview only)"),
    # TEMPORARY (Nov 20): one Kokoro sample build tonight, preview only (never posts). Remove after it runs.
    Job("voice_sample", "reel_voice",   (FRI,), "20:45", live=False, start="2026-11-20", note="TEMP: Kokoro voice sample (preview only)"),
    Job("map_thu",     "reel_map",      (THU,), "17:00", live=True, note="Reel: US map, every state colored by a housing measure"),
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
