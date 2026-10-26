"""Paycheck Math Reels. Every number comes from pm.data and passes its checks first."""
import os
from datetime import date

from . import checks as C
from . import data as D
from . import light as L
from . import templates as T
from .core import DISCLAIMER, DataError, NoContent, Post, with_question
from .video import make_reel, video_checks

GREEN, RED, GOLD = "#3DDC84", "#FF5A5F", "#E8B84A"
UP_RED, DOWN_GREEN, BLUE = "#EF4444", "#16A34A", "#3B82F6"
ICON = {"Eggs": "egg", "Milk": "milk", "Ground beef": "beef", "Bread": "bread", "Coffee": "coffee", "Gas": "gas",
        "Electricity": "bulb", "Your pay": "pay", "Overall prices": "prices", "Rent": "rent", "Groceries": "cart"}
TAGS = "#personalfinance #costofliving #money #inflation"


def _post(key, mp4, cover, caption, rep):
    video_checks(rep, mp4)
    C.image(rep, cover, "reel")
    return Post(key=key, caption=caption, images=[{"reel": mp4, "cover": cover}], media="reel", checks=rep)


def _pct(new, old):
    return (new - old) / old * 100


def _chip(text, color=GOLD):
    return {"abbr": text, "color": color}


# ---------------------------------------------------------------- weekly: mortgage rate

def reel_mortgage(out_dir):
    rep = C.Report("mortgage")
    D.check_series(rep, ["MORTGAGE30"])
    pts = D.series("MORTGAGE30")
    (d0, prev), (d1, now) = pts[-2], pts[-1]
    yago = D.year_ago_checked(rep, "MORTGAGE30")
    wk = now - prev
    up = wk > 0
    hook = ("Mortgage rates", "just went up" if up else ("just dropped" if wk < 0 else "held steady"),
            "red" if up else "green")
    # what the change means on a typical loan (clearly labeled example, standard 30-yr amortization)
    loan = 400_000
    pay = lambda r: loan * (r / 1200) / (1 - (1 + r / 1200) ** -360)
    diff_yr = pay(now) - pay(yago[1])
    label = f"30-yr fixed · {wk:+.2f} this week · {now - yago[1]:+.2f} vs a year ago"
    who = {"abbr": "30Y", "color": GOLD, "name": f"Week of {d1:%b %-d}"}
    tag = "Mortgage rates"
    items = [{"label": "A year ago", "sub": f"{yago[0]:%b %-d, %Y}", "value": yago[1], "icon": "house",
              "value_label": f"{yago[1]:.2f}%", "color": BLUE},
             {"label": "This week", "sub": f"{d1:%b %-d, %Y}", "value": now, "icon": "house",
              "value_label": f"{now:.2f}%", "color": UP_RED if now > yago[1] else DOWN_GREEN}]
    yr_up = now > yago[1]
    # headline describes the comparison the bars show (a year ago vs this week); weekly move goes in the subtitle
    word = "Up From Last Year" if yr_up else ("Down From Last Year" if now < yago[1] else "Same as Last Year")
    sub = (f"30-yr fixed · {wk:+.2f} this week · $400k loan: ${pay(now):,.0f}/mo "
           f"({'+' if diff_yr >= 0 else '-'}${abs(diff_yr):,.0f} vs a year ago)")
    mp4, cover = make_reel(out_dir, "reel_mortgage", hook, lambda p: L.bars(
        "Mortgage Rates {hl}", word, sub, items, "Freddie Mac PMMS", p=p, hl_color=UP_RED if yr_up else DOWN_GREEN),
        tag, f"pmms-{d1}")
    key = f"{d1.isoformat()}-reel-mortgage"
    caption = with_question(
        f"30-year mortgage rate: {now:.2f}% ({wk:+.2f} this week, {now - yago[1]:+.2f} vs a year ago) 🏠\n\n"
        f"On a $400,000 loan, that's about ${pay(now):,.0f}/month in principal + interest, "
        f"{'up' if diff_yr >= 0 else 'down'} ${abs(diff_yr):,.0f}/month from a year ago.",
        "mortgage", key, rate=f"{now:.1f}")
    caption += f"\n\nSource: Freddie Mac Primary Mortgage Market Survey. Example payment excludes taxes/insurance.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#mortgagerates #realestate #homebuying {TAGS}"
    return _post(key, mp4, cover, caption, rep)


# ---------------------------------------------------------------- monthly data, rotating formats

ITEMS = [("APU0000708111", "Eggs", "🥚"), ("APU0000709112", "Milk", "🥛"), ("APU0000703112", "Ground beef", "🥩"),
         ("APU0000702111", "Bread", "🍞"), ("APU0000717311", "Coffee", "☕"), ("APU000074714", "Gas", "⛽"),
         ("APU000072610", "Electricity", "💡")]


def _price_rows(rep):
    D.check_series(rep, [sid for sid, _, _ in ITEMS])
    rows = []
    for sid, name, _ in ITEMS:
        d, v = D.latest(sid)
        ya = D.year_ago_checked(rep, sid)
        ch = _pct(v, ya[1])
        f = (lambda x: f"{x * 100:.1f}¢") if sid == "APU000072610" else (lambda x: f"${x:.2f}")
        rows.append({"name": name, "ch": ch, "sub": f"{f(ya[1])} → {f(v)}"})
    return rows


def _groceries(out_dir, month, rep):
    """Biggest price JUMPS vs a year ago (only items that went up)."""
    rows = sorted([r for r in _price_rows(rep) if r["ch"] > 0.5], key=lambda r: -r["ch"])[:5]
    if len(rows) < 3:
        raise NoContent("Fewer than 3 items rose in price; skipping the price-jumps chart.")
    items = [{"label": r["name"], "sub": r["sub"], "value": r["ch"], "icon": ICON[r["name"]],
              "value_label": f"+{r['ch']:.0f}%"} for r in rows]
    top = rows[0]
    hook = (f"{top['name']} up {top['ch']:.0f}%", "in one year", "red")
    mp4, cover = make_reel(out_dir, "reel_groceries", hook, lambda p: L.bars(
        "Biggest Price {hl}", "Jumps", f"Change vs. a year ago · U.S. average prices, {month:%b %Y}", items,
        f"BLS, {month:%b %Y}", p=p, hl_color="#F97316"), "Prices", f"groceries-{month}")
    lines = "\n".join(f"🔴 {r['name']}: +{r['ch']:.0f}% ({r['sub']})" for r in rows)
    caption = with_question(f"{top['name']}: up {top['ch']:.0f}% from a year ago ({top['sub']}). "
                            f"The biggest jumps:\n\n{lines}", "prices", f"{month}-groceries",
                            item=top["name"].lower())
    caption += f"\n\nSource: U.S. Bureau of Labor Statistics average prices, {month:%B %Y}.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#groceryprices {TAGS}"
    return "groceries", hook, mp4, cover, caption


def _price_drops(out_dir, month, rep):
    """Prices that DROPPED vs a year ago (good-news post)."""
    rows = sorted([r for r in _price_rows(rep) if r["ch"] < -0.5], key=lambda r: r["ch"])[:5]
    if len(rows) < 2:
        raise NoContent("Fewer than 2 items fell in price; skipping the price-drops chart.")
    items = [{"label": r["name"], "sub": r["sub"], "value": -r["ch"], "icon": ICON[r["name"]],
              "value_label": f"-{-r['ch']:.0f}%"} for r in rows]
    top = rows[0]
    hook = (f"{top['name']} down {-top['ch']:.0f}%", "in one year")
    mp4, cover = make_reel(out_dir, "reel_drops", hook, lambda p: L.bars(
        "Prices That {hl}", "Dropped", f"Change vs. a year ago · U.S. average prices, {month:%b %Y}", items,
        f"BLS, {month:%b %Y}", p=p, hl_color=DOWN_GREEN), "Prices", f"drops-{month}")
    lines = "\n".join(f"🟢 {r['name']}: {r['ch']:.0f}% ({r['sub']})" for r in rows)
    caption = with_question(f"{top['name']}: down {-top['ch']:.0f}% from a year ago ({top['sub']}). "
                            f"Everything that got cheaper:\n\n{lines}", "prices", f"{month}-drops",
                            item=top["name"].lower())
    caption += f"\n\nSource: U.S. Bureau of Labor Statistics average prices, {month:%B %Y}.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#groceryprices {TAGS}"
    return "price_drops", hook, mp4, cover, caption


def _minutes(out_dir, month, rep):
    D.check_series(rep, ["CES0500000003"] + [s for s, _, _ in ITEMS])
    wage = D.latest("CES0500000003")[1]
    wage_ya = D.year_ago_checked(rep, "CES0500000003")[1]
    rows = []
    for sid, name, _ in ITEMS[:6]:
        qty = 15 if name == "Gas" else 1
        what = "a 15-gal tank" if name == "Gas" else D.SERIES[sid][0].split("(")[-1].rstrip(")")
        now_min = D.latest(sid)[1] * qty / wage * 60
        ya_min = D.year_ago_checked(rep, sid)[1] * qty / wage_ya * 60
        rows.append({"abbr": name[:3].upper(), "color": "#2B4A3A", "name": f"{name} ({what})", "value": now_min - ya_min,
                     "value_label": f"{now_min:.0f} min", "record": f"was {ya_min:.0f} min a year ago",
                     "good": now_min <= ya_min})
    rows.sort(key=lambda r: -abs(r["value"]))
    gas = next(r for r in rows if r["name"].startswith("Gas"))
    hook = ("Minutes of work", "to buy everyday stuff")
    items = [{"label": r["name"].split(" (")[0], "sub": r["record"].replace(" a year ago", " last yr"),
              "value": float(r["value_label"].split()[0]), "icon": ICON[r["name"].split(" (")[0]],
              "value_label": r["value_label"].replace(" min", "m")} for r in sorted(rows, key=lambda r: -float(r["value_label"].split()[0]))]
    mp4, cover = make_reel(out_dir, "reel_minutes", hook, lambda p: L.bars(
        "Minutes of Work to {hl}", "Buy It", f"At the average wage of ${wage:.2f}/hr · {month:%b %Y} · gas = 15-gal tank",
        items, "BLS prices & wages", p=p, hl_color=BLUE), "Paycheck math", f"minutes-{month}")
    lines = "\n".join(f"{'🔴' if not r['good'] else '🟢'} {r['name']}: {r['value_label']} ({r['record']})" for r in rows)
    caption = with_question(f"At the U.S. average wage of ${wage:.2f}/hr, a 15-gallon tank of gas takes {gas['value_label']} of work "
                            f"({gas['record']}).\n\nEveryday stuff, in minutes of work:\n{lines}",
                            "minutes", f"{month}-minutes")
    caption += f"\n\nSource: BLS average prices and average hourly earnings (all private employees). Pre-tax.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n{TAGS}"
    return "minutes", hook, mp4, cover, caption


def _pay_vs_prices(out_dir, month, rep):
    ids = ["CES0500000003", "CUUR0000SA0", "CUUR0000SEHA", "CUUR0000SAF11", "APU000074714"]
    D.check_series(rep, ids)
    base = date(2020, 1, 1)
    names = {"CES0500000003": "Your pay", "CUUR0000SA0": "Overall prices", "CUUR0000SEHA": "Rent",
             "CUUR0000SAF11": "Groceries", "APU000074714": "Gas"}
    rows = []
    for sid in ids:
        b = D.value_on_or_before(sid, base)
        rep.require(b is not None and b[0] == base, f"{names[sid]}: Jan 2020 baseline", "missing baseline")
        ch = _pct(D.latest(sid)[1], b[1])
        rows.append({"abbr": "PAY" if sid == "CES0500000003" else names[sid][:3].upper(),
                     "color": GREEN if sid == "CES0500000003" else "#2B4A3A", "name": names[sid], "value": ch,
                     "value_label": f"{ch:+.0f}%", "record": "since Jan 2020",
                     "good": sid == "CES0500000003"})
    pay = rows[0]["value"]
    for r in rows[1:]:
        r["good"] = r["value"] <= pay           # green if it rose less than pay
    worst = max(rows[1:], key=lambda r: r["value"])
    hook = (f"{worst['name']} +{worst['value']:.0f}%", f"your pay +{pay:.0f}%", "red" if worst["value"] > pay else "")
    palette = ["#22C55E", "#A855F7", "#3B82F6", "#F97316", "#EF4444"]
    items = [{"label": r["name"], "sub": "since 2020", "value": max(r["value"], 0.1), "icon": ICON[r["name"]],
              "value_label": r["value_label"], "color": palette[i]} for i, r in enumerate(rows)]
    mp4, cover = make_reel(out_dir, "reel_payvs", hook, lambda p: L.bars(
        "Your Pay vs. {hl}", "Prices", f"Change since January 2020, through {month:%b %Y}", items,
        f"BLS, {month:%b %Y}", p=p, hl_color="#EF4444"), "Pay vs prices", f"payvs-{month}")
    lines = "\n".join(f"{'🟢' if r['good'] else '🔴'} {r['name']}: {r['value_label']}" for r in rows)
    caption = with_question(f"Since January 2020, average pay is up {pay:.0f}%. {worst['name']}: up {worst['value']:.0f}%.\n\n"
                            f"{lines}\n\n(Green = rose less than average pay. Red = rose more.)",
                            "paycheck", f"{month}-payvs")
    caption += f"\n\nSource: BLS average hourly earnings and Consumer Price Index (not seasonally adjusted).\n{DISCLAIMER}\n👉 Follow @paycheck_math\n{TAGS}"
    return "payvs", hook, mp4, cover, caption


def _gas(out_dir, month, rep):
    D.check_series(rep, ["APU000074714"])
    d, v = D.latest("APU000074714")
    ya = D.year_ago_checked(rep, "APU000074714")[1]
    ch = _pct(v, ya)
    up = ch > 0
    hook = (f"Gas is {'up' if up else 'down'} {abs(ch):.0f}%", "from a year ago", "red" if up else "")
    who = {"abbr": "GAS", "color": GOLD, "name": f"U.S. average, {d:%B}"}
    yd = date(d.year - 1, d.month, 1)
    items = [{"label": "A year ago", "sub": f"{yd:%B %Y}", "value": ya, "icon": "gas", "value_label": f"${ya:.2f}", "color": BLUE},
             {"label": "Now", "sub": f"{d:%B %Y}", "value": v, "icon": "gas", "value_label": f"${v:.2f}",
              "color": UP_RED if up else DOWN_GREEN}]
    mp4, cover = make_reel(out_dir, "reel_gas", hook, lambda p: L.bars(
        "Gas Prices {hl}", "Went Up" if up else "Came Down",
        f"Regular, U.S. average per gallon · a 15-gal fill-up is ${v * 15:.0f} (was ${ya * 15:.0f})", items,
        f"BLS, {d:%b %Y}", p=p, hl_color=UP_RED if up else DOWN_GREEN), "Gas prices", f"gas-{month}")
    caption = with_question(f"Regular gas averaged ${v:.2f}/gallon in {d:%B}, {'up' if up else 'down'} {abs(ch):.0f}% from ${ya:.2f} a year ago ⛽\n\nA 15-gallon fill-up: ${v * 15:.0f} vs ${ya * 15:.0f}.",
                            "prices", f"{month}-gas", item="gas")
    caption += f"\n\nSource: BLS average price data, unleaded regular.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#gasprices {TAGS}"
    return "gas", hook, mp4, cover, caption


# Single-item trend lines: (series, name, unit text, value format, up_is_good)
TRENDS = [
    ("APU0000708111", "Eggs", "Dozen eggs", lambda v: f"${v:.2f}", False),
    ("APU0000703112", "Ground beef", "Ground beef, per lb", lambda v: f"${v:.2f}", False),
    ("APU0000717311", "Coffee", "Coffee, per lb", lambda v: f"${v:.2f}", False),
    ("APU0000709112", "Milk", "Milk, per gallon", lambda v: f"${v:.2f}", False),
    ("APU0000702111", "Bread", "White bread, per lb", lambda v: f"${v:.2f}", False),
    ("APU000072610", "Electricity", "Electricity, per kWh", lambda v: f"{v * 100:.1f}¢", False),
    ("CES0500000003", "Hourly pay", "Average hourly pay (private sector)", lambda v: f"${v:.2f}", True),
]


def _trend_format(sid, name, unit, fmt, up_good):
    def build(out_dir, month, rep):
        D.check_series(rep, [sid])
        d, v = D.latest(sid)
        ya = D.year_ago_checked(rep, sid)
        ch = _pct(v, ya[1])
        good = (ch > 0) == up_good
        start = date(d.year - 3, d.month, 1)
        pts = [p for p in D.series(sid) if p[0] >= start]
        rep.require(len(pts) >= 30, f"{name}: 3-year history", f"only {len(pts)} months")
        mi = [k for k, (dd, _) in enumerate(pts) if dd == ya[0]][0]
        hook = (f"{name} {'up' if ch > 0 else 'down'} {abs(ch):.0f}%", "in one year", "" if good else "red")
        word = f"{'Up' if ch > 0 else 'Down'} {abs(ch):.0f}%"
        mp4, cover = make_reel(out_dir, f"reel_trend_{name.lower().replace(' ', '_')}", hook, lambda p: L.line(
            f"{name} {{hl}}", word, f"{unit} · U.S. average · vs. a year ago", pts, fmt, f"BLS, {d:%b %Y}",
            color=BLUE if up_good else "#F97316", marker=(mi, f"a year ago {fmt(ya[1])}"), p=p,
            hl_color=DOWN_GREEN if good else UP_RED), "Trend", f"trend-{sid}-{month}")
        caption = with_question(
            f"{unit}: {fmt(v)} in {d:%B %Y}, {'up' if ch > 0 else 'down'} {abs(ch):.0f}% from {fmt(ya[1])} a year ago "
            f"{'📈' if ch > 0 else '📉'}", "paycheck" if up_good else "prices", f"{month}-trend-{sid}", item=name.lower())
        caption += f"\n\nSource: U.S. Bureau of Labor Statistics.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n{TAGS}"
        return f"trend_{name.lower().replace(' ', '_')}", hook, mp4, cover, caption, abs(ch)
    build.__name__ = f"_trend_{name.lower().replace(' ', '_')}"
    return build


FORMATS = [_pay_vs_prices, _groceries, _price_drops, _minutes, _gas] + [_trend_format(*t) for t in TRENDS]


def _yoy_size(fmt):
    """Most dramatic trend first (bigger moves get more attention)."""
    name = fmt.__name__
    for sid, n, *_ in TRENDS:
        if name.endswith(n.lower().replace(" ", "_")):
            try:
                return abs(_pct(D.latest(sid)[1], D.year_ago(sid)[1]))
            except Exception:
                return 0
    return 999   # the core chart formats always go first


def reel_monthly(out_dir, posted=None):
    """Posts the next not-yet-posted format for the latest BLS month; skips once all are used."""
    month = D.latest("CUUR0000SA0")[0]
    posted = posted or {}
    for fmt in sorted(FORMATS, key=_yoy_size, reverse=True):
        name = fmt.__name__.strip("_")
        key = f"{month:%Y-%m}-reel-{name}"
        if key in posted:
            continue
        rep = C.Report(name)
        try:
            _, hook, mp4, cover, caption, *_ = fmt(os.path.join(out_dir), month, rep)
        except NoContent:
            continue          # this format doesn't apply this month (e.g. nothing got cheaper)
        return _post(key, mp4, cover, caption, rep)
    raise NoContent(f"All monthly formats for {month:%B %Y} already posted; waiting for new BLS data.")


# ---------------------------------------------------------------- monthly: find your state (share-first)

def reel_find_state(out_dir, posted=None):
    """All 50 states + DC on one screen, ranked by average weekly pay. Built for 'find your state, send it
    to a friend'. Posts once per BLS state data month; idles until the next release."""
    rep = C.Report("find_state")
    month, rows = D.check_state_pay(rep)
    if not rows:
        raise DataError("State pay data failed checks: " + "; ".join(i["detail"] for i in rep.blocked))
    key = f"{month:%Y-%m}-reel-find_state"
    if key in (posted or {}):
        raise NoContent(f"Find Your State for {month:%B %Y} already posted; waiting for new BLS state data.")
    prelim = any(month in D.state_weekly_pay()[r["fips"]]["prelim"] for r in rows)
    items = []
    for k, r in enumerate(rows):
        yoy = r["yoy"]
        items.append({"label": r["name"], "value_label": f"${r['value']:,.0f}",
                      "note": "" if yoy is None else f"{yoy:+.1f}%",
                      "note_color": DOWN_GREEN if (yoy or 0) >= 0 else UP_RED,
                      "color": DOWN_GREEN if k < 10 else (UP_RED if k >= len(rows) - 10 else "#1F2937")})
    top, low = rows[0], rows[-1]
    gap = top["value"] - low["value"]
    hook = ("Find your state", "average weekly pay")
    sub = f"Avg. weekly pay, pre-tax · {month:%b %Y} · % = vs. a year ago"
    mp4, cover = make_reel(out_dir, "reel_find_state", hook, lambda p: L.board(
        "Find Your {hl}", "State", sub, items, f"BLS, {month:%b %Y}{' (preliminary)' if prelim else ''}", p=p,
        hl_color=BLUE), "Find your state", f"states-{month}", hold=7.0)
    medal = ["🥇", "🥈", "🥉", "4.", "5."]
    lines = "\n".join(f"{medal[k]} {r['name']}: ${r['value']:,.0f}/week" for k, r in enumerate(rows[:5]))
    bottom = "\n".join(f"{len(rows) - 2 + k}. {r['name']}: ${r['value']:,.0f}/week" for k, r in enumerate(rows[-3:]))
    caption = with_question(
        f"Average weekly pay by state, {month:%B %Y} (private-sector jobs, before taxes) 💵\n\n"
        f"Highest:\n{lines}\n\nLowest:\n{bottom}\n\n"
        f"That's a ${gap:,.0f} gap every week between {top['name']} and {low['name']}.",
        "states", key)
    caption += (f"\n\n📤 Send this to someone in {low['name']}."
                f"\n\nSource: U.S. Bureau of Labor Statistics, State and Metro Area Employment (CES): average weekly "
                f"earnings of all employees, total private, not seasonally adjusted."
                f"{f' {month:%B %Y} figures are preliminary.' if prelim else ''}"
                f"\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#paycheck #salary #wages {TAGS}")
    return _post(key, mp4, cover, caption, rep)


BUILDERS = {"reel_mortgage": lambda out_dir, posted=None: reel_mortgage(out_dir),
            "reel_monthly": reel_monthly,
            "reel_find_state": reel_find_state}
