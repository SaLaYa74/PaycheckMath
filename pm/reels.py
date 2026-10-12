"""Paycheck Math Reels. Every number comes from pm.data and passes its checks first."""
import os
from datetime import date

from . import checks as C
from . import data as D
from . import templates as T
from .core import DISCLAIMER, NoContent, Post, with_question
from .video import make_reel, video_checks

GREEN, RED, GOLD = "#3DDC84", "#FF5A5F", "#E8B84A"
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
    mp4, cover = make_reel(out_dir, "reel_mortgage", hook, lambda p: T.one_stat(
        hook, f"{now:.2f}%", label, who, "red" if up else "green", tag=tag, source="Freddie Mac PMMS", p=p,
        note=f"On a $400k loan: {'+' if diff_yr >= 0 else '-'}${abs(diff_yr):,.0f}/mo vs a year ago"), tag, f"pmms-{d1}")
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


def _groceries(out_dir, month, rep):
    D.check_series(rep, [s for s, _, _ in ITEMS])
    rows = []
    for sid, name, _ in ITEMS:
        d, v = D.latest(sid)
        ya = D.year_ago_checked(rep, sid)
        ch = _pct(v, ya[1])
        unit = D.SERIES[sid][0].split("(")[-1].rstrip(")")
        rows.append({"abbr": name[:3].upper(), "color": "#2B4A3A", "name": name, "value": ch,
                     "value_label": f"{ch:+.0f}%", "record": f"${ya[1]:.2f} → ${v:.2f} per {unit}"})
    rows.sort(key=lambda r: -r["value"])
    top = rows[0]
    hook = (f"{top['name']} {'up' if top['value'] > 0 else 'down'} {abs(top['value']):.0f}%", "in one year",
            "red" if top["value"] > 0 else "")
    mp4, cover = make_reel(out_dir, "reel_groceries", hook, lambda p: T.bar_ranking(
        "Everyday prices<br><em>vs. a year ago</em>", f"U.S. average prices, {month:%B %Y}", rows,
        tag="Prices", source="Bureau of Labor Statistics", size="reel", p=p, hook=hook, glance=True, invert=True),
        "Prices", f"groceries-{month}")
    lines = "\n".join(f"{'🔴' if r['value'] > 0 else '🟢'} {r['name']}: {r['value_label']} ({r['record']})" for r in rows)
    caption = with_question(f"What everyday stuff costs now vs. a year ago 🛒\n\n{lines}", "prices", f"{month}-groceries",
                            item=top["name"].lower())
    caption += f"\n\nSource: U.S. Bureau of Labor Statistics average prices, {month:%B %Y}.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n#groceryprices {TAGS}"
    return "groceries", hook, mp4, cover, caption


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
    mp4, cover = make_reel(out_dir, "reel_minutes", hook, lambda p: T.bar_ranking(
        "Minutes of work<br><em>to buy it</em>", f"At the average hourly wage (${wage:.2f}/hr), {month:%B %Y}",
        rows, tag="Paycheck math", source="BLS prices & wages", size="reel", p=p, hook=hook, glance=True,
        note="Bar = change vs. a year ago"), "Paycheck math", f"minutes-{month}")
    lines = "\n".join(f"{'🔴' if not r['good'] else '🟢'} {r['name']}: {r['value_label']} ({r['record']})" for r in rows)
    caption = with_question(f"How many minutes of work it takes to buy everyday stuff ⏱️\n\nAt the U.S. average wage of ${wage:.2f}/hr:\n{lines}",
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
    mp4, cover = make_reel(out_dir, "reel_payvs", hook, lambda p: T.bar_ranking(
        "Your pay<br><em>vs. prices</em>", f"Change since January 2020, through {month:%B %Y}", rows,
        tag="Pay vs prices", source="Bureau of Labor Statistics", size="reel", p=p, hook=hook, glance=True,
        diverging=False), "Pay vs prices", f"payvs-{month}")
    lines = "\n".join(f"{'🟢' if r['good'] else '🔴'} {r['name']}: {r['value_label']}" for r in rows)
    caption = with_question(f"Since January 2020, has your paycheck kept up? 💵\n\n{lines}\n\n(Green = rose less than average pay. Red = rose more.)",
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
    mp4, cover = make_reel(out_dir, "reel_gas", hook, lambda p: T.one_stat(
        hook, f"${v:.2f}", f"per gallon · was ${ya:.2f}", who, "red" if up else "green", tag="Gas prices",
        source="Bureau of Labor Statistics", p=p, note=f"A 15-gallon fill-up: ${v * 15:.0f} (was ${ya * 15:.0f})"),
        "Gas prices", f"gas-{month}")
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
        mp4, cover = make_reel(out_dir, f"reel_trend_{name.lower().replace(' ', '_')}", hook, lambda p: T.line_chart(
            hook, pts, fmt, tag="Price trend" if not up_good else "Paycheck trend", source="Bureau of Labor Statistics",
            color="green" if good else "red", p=p, end_label=f"{unit} · U.S. average · last 3 years",
            marker=(mi, f"a year ago {fmt(ya[1])}")), "Trend", f"trend-{sid}-{month}")
        caption = with_question(
            f"{unit}: {fmt(v)} in {d:%B %Y}, {'up' if ch > 0 else 'down'} {abs(ch):.0f}% from {fmt(ya[1])} a year ago "
            f"{'📈' if ch > 0 else '📉'}", "paycheck" if up_good else "prices", f"{month}-trend-{sid}", item=name.lower())
        caption += f"\n\nSource: U.S. Bureau of Labor Statistics.\n{DISCLAIMER}\n👉 Follow @paycheck_math\n{TAGS}"
        return f"trend_{name.lower().replace(' ', '_')}", hook, mp4, cover, caption, abs(ch)
    build.__name__ = f"_trend_{name.lower().replace(' ', '_')}"
    return build


FORMATS = [_pay_vs_prices, _groceries, _minutes, _gas] + [_trend_format(*t) for t in TRENDS]


def _yoy_size(fmt):
    """Most dramatic trend first (bigger moves get more attention)."""
    name = fmt.__name__
    for sid, n, *_ in TRENDS:
        if name.endswith(n.lower().replace(" ", "_")):
            try:
                return abs(_pct(D.latest(sid)[1], D.year_ago(sid)[1]))
            except Exception:
                return 0
    return 999   # the four core formats always go first


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
        _, hook, mp4, cover, caption, *_ = fmt(os.path.join(out_dir), month, rep)
        return _post(key, mp4, cover, caption, rep)
    raise NoContent(f"All monthly formats for {month:%B %Y} already posted; waiting for new BLS data.")


BUILDERS = {"reel_mortgage": lambda out_dir, posted=None: reel_mortgage(out_dir),
            "reel_monthly": reel_monthly}
