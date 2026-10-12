"""Official economic data for Paycheck Math, straight from the agencies that publish it.

- Bureau of Labor Statistics public API (prices, rent, groceries, gas, wages, inflation)
- Freddie Mac Primary Mortgage Market Survey file (30-year mortgage rate, weekly)

Checks: data is current, values are in a plausible range, and the latest move vs. the
prior period is realistic (catches typos/glitches). Anything failing blocks the post.
"""
import csv
import io
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime

UA = {"User-Agent": "PaycheckMath/1.0 (public-data charts; contact via instagram @paycheckmath)"}
BLS_API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
PMMS_CSV = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"

# id: (label, unit, source, max_age_days, plausible (lo, hi), max realistic one-period move as a fraction)
SERIES = {
    "MORTGAGE30": ("30-year mortgage rate", "%", "Freddie Mac", 12, (2, 12), 0.10),
    "APU000074714": ("Regular gas (gallon)", "$", "BLS", 80, (1.5, 7), 0.20),
    "CUUR0000SA0": ("Overall prices (CPI)", "index", "BLS", 80, (200, 500), 0.03),
    "CUUR0000SEHA": ("Rent", "index", "BLS", 80, (200, 700), 0.03),
    "CUUR0000SAF11": ("Groceries", "index", "BLS", 80, (200, 450), 0.04),
    "CES0500000003": ("Average hourly pay", "$", "BLS", 80, (20, 60), 0.03),
    "APU0000708111": ("Eggs (dozen)", "$", "BLS", 80, (0.8, 8), 0.40),
    "APU0000709112": ("Milk (gallon)", "$", "BLS", 80, (2, 7), 0.15),
    "APU0000703112": ("Ground beef (lb)", "$", "BLS", 80, (3, 12), 0.15),
    "APU0000702111": ("Bread (lb)", "$", "BLS", 80, (1, 4), 0.15),
    "APU0000717311": ("Coffee (lb)", "$", "BLS", 80, (3, 15), 0.20),
    "APU000072610": ("Electricity (kWh)", "$", "BLS", 80, (0.08, 0.35), 0.15),
}
BLS_IDS = [s for s, v in SERIES.items() if v[2] == "BLS"]


def _get(url, data=None, tries=4, timeout=60):
    headers = {**UA, **({"Content-Type": "application/json"} if data else {})}
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == tries - 1:
                raise
        time.sleep(3 * (attempt + 1))


_cache = {}


def _load_bls():
    """One request for every BLS series (the free API allows 25 series and 10 years per request)."""
    year = date.today().year
    body = json.dumps({"seriesid": BLS_IDS, "startyear": str(year - 9), "endyear": str(year)}).encode()
    d = json.loads(_get(BLS_API, data=body))
    if d.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API: {d.get('status')}: {' '.join(d.get('message', []))}")
    for s in d["Results"]["series"]:
        pts = []
        for p in s["data"]:
            if p["period"].startswith("M") and p["period"] != "M13" and p["value"] not in ("-", ""):
                pts.append((date(int(p["year"]), int(p["period"][1:]), 1), float(p["value"])))
        _cache[s["seriesID"]] = sorted(pts)


def _load_pmms():
    rows = csv.DictReader(io.StringIO(_get(PMMS_CSV).decode()))
    pts = []
    for r in rows:
        if r.get("pmms30", "").strip():
            pts.append((datetime.strptime(r["date"], "%m/%d/%Y").date(), float(r["pmms30"])))
    _cache["MORTGAGE30"] = sorted(pts)


def series(sid):
    """[(date, value)] oldest→newest."""
    if sid not in _cache:
        _load_pmms() if sid == "MORTGAGE30" else _load_bls()
    return _cache[sid]


def latest(sid):
    return series(sid)[-1]


def value_on_or_before(sid, when):
    pts = [p for p in series(sid) if p[0] <= when]
    return pts[-1] if pts else None


def year_ago(sid):
    d, _ = latest(sid)
    return value_on_or_before(sid, date(d.year - 1, d.month, min(d.day, 28)))


def check_series(rep, ids):
    """Freshness, plausible range and realistic latest move for each series used in a post."""
    today = date.today()
    for sid in ids:
        label, unit, src, max_age, (lo, hi), max_move = SERIES[sid]
        pts = series(sid)
        if not rep.require(len(pts) >= 13, f"{label}: enough history", f"only {len(pts)} data points from {src}"):
            continue
        (d0, v0), (d1, v1) = pts[-2], pts[-1]
        rep.require(lo <= v1 <= hi, f"{label}: value plausible", f"{v1} outside {lo}-{hi}")
        rep.require((today - d1).days <= max_age, f"{label}: data is current", f"latest {src} data is {d1}")
        move = abs(v1 - v0) / v0
        rep.require(move <= max_move, f"{label}: realistic change", f"{v0} → {v1} ({move:.0%}) looks like a data error")
