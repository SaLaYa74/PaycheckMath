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

UA = {"User-Agent": "PaycheckMath/1.0 (public-data charts; contact via instagram @paycheck_math)"}
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
    # Added Oct 26 2026 (Jarvis) for more single-item trend Reels; ranges bracket the 2016-2026 history.
    "APU0000704111": ("Bacon (lb)", "$", "BLS", 80, (3, 12), 0.15),
    "APU0000712311": ("Tomatoes (lb)", "$", "BLS", 80, (1, 4), 0.25),
    "APU0000701111": ("Flour (lb)", "$", "BLS", 80, (0.3, 1.2), 0.15),
    "APU000072620": ("Utility gas (therm)", "$", "BLS", 80, (0.7, 3.5), 0.25),
    # Added Oct 28 2026 for comparison charts: price per pound of common proteins, and gas by Census region.
    "APU0000706111": ("Whole chicken (lb)", "$", "BLS", 80, (1, 4), 0.15),
    "APU0000FF1101": ("Chicken breast, boneless (lb)", "$", "BLS", 80, (2.5, 8), 0.15),
    "APU0000FD3101": ("Pork chops (lb)", "$", "BLS", 80, (2.5, 8), 0.15),
    "APU0000703511": ("Round steak, boneless (lb)", "$", "BLS", 80, (5, 15), 0.15),
    "APU010074714": ("Regular gas, Northeast (gallon)", "$", "BLS", 80, (1.5, 8), 0.20),
    "APU020074714": ("Regular gas, Midwest (gallon)", "$", "BLS", 80, (1.5, 8), 0.20),
    "APU030074714": ("Regular gas, South (gallon)", "$", "BLS", 80, (1.5, 8), 0.20),
    "APU040074714": ("Regular gas, West (gallon)", "$", "BLS", 80, (1.5, 8), 0.20),
}
BLS_IDS = [s for s, v in SERIES.items() if v[2] == "BLS"]
assert len(BLS_IDS) <= 25, "the free BLS API takes at most 25 series per request; split _load_bls first"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"


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


def _plain_get(url, tries=3, timeout=45):
    """GET without our custom User-Agent: FRED and the IMF drop or refuse requests that carry it."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
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


def year_ago_checked(rep, sid):
    """The value from exactly one year before the latest point. Blocks the post if that exact
    month (or, for weekly data, a week within 7 days) is missing, rather than silently comparing
    against the wrong period."""
    d, _ = latest(sid)
    label = SERIES[sid][0]
    target = date(d.year - 1, d.month, min(d.day, 28))
    ya = value_on_or_before(sid, target)
    if sid == "MORTGAGE30":
        ok = ya is not None and abs((target - ya[0]).days) <= 7
    else:
        ok = ya is not None and (ya[0].year, ya[0].month) == (d.year - 1, d.month)
    rep.require(ok, f"{label}: year-ago comparison uses the same period",
                f"wanted {target:%b %Y}, nearest available is {ya[0] if ya else None}")
    return ya


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


def fred_check(rep, ids, when):
    """Second source for comparison charts: the St. Louis Fed (FRED) republishes these BLS series through its
    own pipeline. Every value we chart for month `when` must match FRED's to the published 3 decimals."""
    try:
        rows = list(csv.DictReader(io.StringIO(_plain_get(FRED_CSV.format(",".join(ids))).decode())))
    except Exception as e:
        rep.require(False, "FRED cross-check reachable", str(e)[:120])
        return
    row = next((r for r in rows if r.get("observation_date") == when.isoformat()), None)
    if not rep.require(row is not None, f"FRED has {when:%b %Y}", "FRED hasn't published this month yet"):
        return
    for sid in ids:
        mine = value_on_or_before(sid, when)
        theirs = row.get(sid, "")
        ok = mine is not None and mine[0] == when and theirs not in ("", ".") and abs(float(theirs) - mine[1]) < 0.0015
        rep.require(ok, f"{SERIES[sid][0]}: BLS matches FRED", f"BLS {mine} vs FRED {theirs!r}")


# ---------------- countries (IMF World Economic Outlook, checked against the World Bank) ----------------

# ISO3: (label, flag code)
COUNTRIES = {"USA": ("U.S.", "us"), "CAN": ("Canada", "ca"), "MEX": ("Mexico", "mx"), "BRA": ("Brazil", "br"),
             "GBR": ("U.K.", "gb"), "DEU": ("Germany", "de"), "FRA": ("France", "fr"), "JPN": ("Japan", "jp"),
             "CHN": ("China", "cn"), "IND": ("India", "in")}
IMF_URL = "https://www.imf.org/external/datamapper/api/v1/{}/{}?periods={}"
WB_URL = "https://api.worldbank.org/v2/country/{}/indicator/{}?format=json&date={}&per_page=100"


def world_inflation(rep):
    """(year, {iso3: % change in consumer prices}) for the latest year the World Bank has actual data.
    Numbers shown are the IMF's (complete, one methodology). Each must be within 1 point of the World Bank's
    figure; the U.S. (often missing at the World Bank) must match our own BLS CPI annual average within 0.3."""
    iso = list(COUNTRIES)
    year = None
    for y in (date.today().year - 1, date.today().year - 2):
        wb = json.loads(_plain_get(WB_URL.format(";".join(iso), "FP.CPI.TOTL.ZG", y)))
        got = {r["countryiso3code"]: r["value"] for r in (wb[1] if len(wb) > 1 and wb[1] else []) if r["value"] is not None}
        if len(got) >= len(iso) - 2:
            year = y
            break
    if not rep.require(year is not None, "World Bank has a recent full year", "no year with data for most countries"):
        return None, {}
    imf = json.loads(_plain_get(IMF_URL.format("PCPIPCH", "/".join(iso), year)))["values"]["PCPIPCH"]
    out = {}
    for c in iso:
        v = (imf.get(c) or {}).get(str(year))
        if not rep.require(v is not None, f"{COUNTRIES[c][0]}: IMF {year} inflation", "missing"):
            continue
        rep.require(-5 <= v <= 60, f"{COUNTRIES[c][0]}: inflation plausible", f"{v}")
        if c in got:
            rep.require(abs(v - got[c]) <= 1.0, f"{COUNTRIES[c][0]}: IMF matches World Bank",
                        f"IMF {v} vs World Bank {got[c]:.2f}")
        elif c == "USA":
            # Average of the months BLS has in both years (2025 has no October: the shutdown stopped collection).
            by = {(d.year, d.month): x for d, x in series("CUUR0000SA0")}
            months = [m for m in range(1, 13) if (year, m) in by and (year - 1, m) in by]
            bls = ((sum(by[(year, m)] for m in months) / sum(by[(year - 1, m)] for m in months) - 1) * 100
                   if len(months) >= 10 else None)
            rep.require(bls is not None and abs(v - bls) <= 0.3, "U.S.: IMF matches BLS CPI (yearly average)",
                        f"IMF {v} vs BLS {bls}")
        else:
            rep.require(False, f"{COUNTRIES[c][0]}: second source", "not in World Bank data")
        out[c] = v
    return year, out


# ---------------- state pay (BLS State and Metro Area Employment, CES) ----------------

# FIPS: (state, postal abbreviation). All 50 states + DC.
STATES = {
    "01": ("Alabama", "AL"), "02": ("Alaska", "AK"), "04": ("Arizona", "AZ"), "05": ("Arkansas", "AR"),
    "06": ("California", "CA"), "08": ("Colorado", "CO"), "09": ("Connecticut", "CT"), "10": ("Delaware", "DE"),
    "11": ("D.C.", "DC"), "12": ("Florida", "FL"), "13": ("Georgia", "GA"), "15": ("Hawaii", "HI"),
    "16": ("Idaho", "ID"), "17": ("Illinois", "IL"), "18": ("Indiana", "IN"), "19": ("Iowa", "IA"),
    "20": ("Kansas", "KS"), "21": ("Kentucky", "KY"), "22": ("Louisiana", "LA"), "23": ("Maine", "ME"),
    "24": ("Maryland", "MD"), "25": ("Massachusetts", "MA"), "26": ("Michigan", "MI"), "27": ("Minnesota", "MN"),
    "28": ("Mississippi", "MS"), "29": ("Missouri", "MO"), "30": ("Montana", "MT"), "31": ("Nebraska", "NE"),
    "32": ("Nevada", "NV"), "33": ("New Hampshire", "NH"), "34": ("New Jersey", "NJ"), "35": ("New Mexico", "NM"),
    "36": ("New York", "NY"), "37": ("North Carolina", "NC"), "38": ("North Dakota", "ND"), "39": ("Ohio", "OH"),
    "40": ("Oklahoma", "OK"), "41": ("Oregon", "OR"), "42": ("Pennsylvania", "PA"), "44": ("Rhode Island", "RI"),
    "45": ("South Carolina", "SC"), "46": ("South Dakota", "SD"), "47": ("Tennessee", "TN"), "48": ("Texas", "TX"),
    "49": ("Utah", "UT"), "50": ("Vermont", "VT"), "51": ("Virginia", "VA"), "53": ("Washington", "WA"),
    "54": ("West Virginia", "WV"), "55": ("Wisconsin", "WI"), "56": ("Wyoming", "WY"),
}
# Average weekly earnings of all employees, total private, not seasonally adjusted.
STATE_WEEKLY = "SMU{}000000500000011"
STATE_WEEKLY_RANGE = (700, 2800)    # $/week; anything outside is a data error
STATE_YOY_RANGE = (-12, 15)         # % change vs. a year ago; outside = likely a glitch or series break
_state_cache = {}


def state_weekly_pay():
    """{fips: {"pts": [(date, value)] oldest→newest, "prelim": {date, ...}}} for all 51.
    The free API allows 25 series per request, so this is 3 requests."""
    if _state_cache:
        return _state_cache
    year = date.today().year
    fips = list(STATES)
    for i in range(0, len(fips), 25):
        ids = [STATE_WEEKLY.format(f) for f in fips[i:i + 25]]
        body = json.dumps({"seriesid": ids, "startyear": str(year - 2), "endyear": str(year)}).encode()
        d = json.loads(_get(BLS_API, data=body))
        if d.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API: {d.get('status')}: {' '.join(d.get('message', []))}")
        for s in d["Results"]["series"]:
            pts, prelim = [], set()
            for p in s["data"]:
                if p["period"].startswith("M") and p["period"] != "M13" and p["value"] not in ("-", ""):
                    when = date(int(p["year"]), int(p["period"][1:]), 1)
                    pts.append((when, float(p["value"])))
                    if any(f.get("code") == "P" for f in p.get("footnotes") or []):
                        prelim.add(when)
            _state_cache[s["seriesID"][3:5]] = {"pts": sorted(pts), "prelim": prelim}
    return _state_cache


def check_state_pay(rep):
    """All 51 present, same latest month everywhere, current, plausible values, exact year-ago month,
    realistic year-over-year change. Returns (month, rows sorted high→low) where each row is
    dict(fips, name, abbr, value, year_ago, yoy)."""
    data = state_weekly_pay()
    missing = [STATES[f][1] for f in STATES if not data.get(f, {}).get("pts")]
    rep.require(not missing, "State pay: all 50 states + DC present", f"no data for {missing}")
    extra = sorted(set(data) - set(STATES))
    rep.require(not extra, "State pay: no unexpected series", f"unexpected FIPS {extra}")
    if missing:
        return None, []
    latest = {f: data[f]["pts"][-1][0] for f in STATES}
    month = max(latest.values())
    behind = [f"{STATES[f][1]} ({d:%b %Y})" for f, d in latest.items() if d != month]
    rep.require(not behind, "State pay: same latest month for every state", f"{month:%b %Y} for most, but {behind}")
    rep.require((date.today() - month).days <= 80, "State pay: data is current", f"latest BLS state data is {month:%b %Y}")
    lo, hi = STATE_WEEKLY_RANGE
    ylo, yhi = STATE_YOY_RANGE
    rows, no_ya = [], []
    for f, (name, abbr) in STATES.items():
        d, v = data[f]["pts"][-1]
        rep.require(lo <= v <= hi, f"{abbr}: weekly pay plausible", f"${v:,.2f} outside ${lo:,}-${hi:,}")
        ya = next((x for dd, x in data[f]["pts"] if (dd.year, dd.month) == (d.year - 1, d.month)), None)
        yoy = None
        if ya is None:
            no_ya.append(abbr)
        else:
            yoy = (v - ya) / ya * 100
            rep.require(ylo <= yoy <= yhi, f"{abbr}: realistic change vs. a year ago",
                        f"${ya:,.2f} → ${v:,.2f} ({yoy:+.1f}%) looks like a data error")
        rows.append({"fips": f, "name": name, "abbr": abbr, "value": v, "year_ago": ya, "yoy": yoy})
    rep.expect(not no_ya, "State pay: year-ago month available for every state", f"missing {month.year - 1} value for {no_ya}")
    rows.sort(key=lambda r: -r["value"])
    rep.require(len({r["name"] for r in rows}) == 51, "State pay: 51 unique rows", f"{len(rows)} rows")
    return month, rows
