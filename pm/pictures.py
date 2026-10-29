"""Paycheck Math picture posts (still images and swipeable carousels), for the feed between Reels.

Reels win on reach; pictures and carousels win on saves ("I'll come back to this"), and saves are what
Instagram reads as "useful". Each format posts once per BLS data month, like the monthly Reel rotation.
  receipt    : one picture. The same grocery basket at January 2020 prices vs. now, as a store receipt.
  cheatsheet : a 6-slide carousel. "Your money this month": prices, pay, mortgage rate, gas, in one swipe.
  protein / gas_regions / world_inflation : simple side-by-side comparisons (owner, Oct 28: "people like
               comparisons"). Every price is also checked against FRED's copy; countries against the World Bank.
Every number goes through the same pm.data checks as the Reels.
"""
import base64
import os
from datetime import date
from html import escape

from . import checks as C
from . import data as D
from . import light as L
from .core import DISCLAIMER, NoContent, Post, with_question
from .reels import BLUE, DOWN_GREEN, ICON, RELEASE_ROWS, TAGS, UP_RED, _pct, _yoy
from .render import html_to_png
from .templates import mascot_svg

BASE = date(2020, 1, 1)
PAY = "CES0500000003"
CPI = "CUUR0000SA0"
# (series, receipt line). One unit each, exactly as BLS prices it.
BASKET = [("APU0000708111", "EGGS, DOZEN"), ("APU0000709112", "MILK, GALLON"), ("APU0000703112", "GROUND BEEF, 1 LB"),
          ("APU0000704111", "BACON, 1 LB"), ("APU0000717311", "COFFEE, 1 LB"), ("APU0000702111", "WHITE BREAD, 1 LB"),
          ("APU0000712311", "TOMATOES, 1 LB"), ("APU0000701111", "FLOUR, 1 LB")]
MONO = '<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=block" rel="stylesheet">'


def _render(out_dir, name, html):
    path = html_to_png(html, os.path.join(out_dir, f"{name}.png"), "feed")
    return {"feed": path}


def _post(key, images, caption, rep):
    for img in images:
        C.image(rep, img["feed"], "feed")
    return Post(key=key, caption=caption, images=images, media="feed", checks=rep)


def _at(rep, sid, when, label):
    """Value for exactly that month, or block the post."""
    v = D.value_on_or_before(sid, when)
    rep.require(v is not None and (v[0].year, v[0].month) == (when.year, when.month),
                f"{label}: value for {when:%b %Y}", f"nearest is {v[0] if v else None}")
    return v[1] if v else 0.0


# ---------------------------------------------------------------- the grocery receipt

def receipt(out_dir, month, rep):
    D.check_series(rep, [sid for sid, _ in BASKET] + [PAY])
    rows = []
    for sid, line in BASKET:
        rep.require(D.latest(sid)[0] == month, f"{line}: same month as the CPI release", f"latest {D.latest(sid)[0]}")
        rows.append((line, round(_at(rep, sid, BASE, line), 2), round(_at(rep, sid, month, line), 2)))
    then, now = round(sum(r[1] for r in rows), 2), round(sum(r[2] for r in rows), 2)   # totals = sum of the printed lines
    ch = _pct(now, then)
    pay0, pay1 = _at(rep, PAY, BASE, "Hourly pay"), _at(rep, PAY, month, "Hourly pay")
    pch = _pct(pay1, pay0)
    rep.require(0 < then < now * 3 and 0 < now < then * 3, "basket totals plausible", f"{then:.2f} → {now:.2f}")
    up = ch > 0
    stamp = UP_RED if up else DOWN_GREEN
    lines = "".join(f'<div class="r"><span>{escape(n)}</span><b>${a:.2f}</b><b>${b:.2f}</b></div>' for n, a, b in rows)
    css = """<style>
.rc{position:relative;margin:30px auto 0;width:900px;background:#fff;padding:44px 56px 70px;transform:rotate(-1.2deg);
    font-family:"Courier Prime",monospace;color:#1F2937;box-shadow:0 18px 40px rgba(0,0,0,.12);
    -webkit-mask:linear-gradient(#000 0 0) top/100% calc(100% - 22px) no-repeat,
                 conic-gradient(from -45deg at bottom,#0000,#000 1deg 89deg,#0000 90deg) bottom/44px 22px repeat-x}
.hd{text-align:center;font-weight:700;font-size:40px;letter-spacing:3px}
.sm{text-align:center;font-size:26px;color:#6B7280;margin-top:4px}
.dash{border-top:4px dashed #9CA3AF;margin:20px 0}
.r{display:grid;grid-template-columns:1fr 170px 170px;font-size:34px;line-height:1.7}
.r b{text-align:right}
.r.h{font-size:24px;color:#6B7280;line-height:1.3}
.tot{display:grid;grid-template-columns:1fr 170px 170px;font-size:42px;font-weight:700}
.tot b{text-align:right}
.stamp{display:table;margin:26px auto 0;transform:rotate(-6deg);border:7px solid var(--c);color:var(--c);
       font-family:"Baloo 2";font-weight:800;font-size:64px;line-height:1;padding:10px 26px 4px;border-radius:14px}
.pay{margin:auto 0 0;font-size:36px;font-weight:800;text-align:center}
.pay em{font-style:normal;color:var(--p)}
</style>"""
    body = f'''{MONO}{css}<div class="t" style="--hl:{stamp}">Your Grocery {{hl}}</div>
<div class="s">The same 8 items, at U.S. average prices</div>
<div class="rc"><div class="hd">PAYCHECK MATH MARKET</div><div class="sm">January 2020 vs. {month:%B %Y}</div>
<div class="dash"></div><div class="r h"><span>ITEM</span><b>JAN 2020</b><b>{month:%b %Y}</b></div>{lines}
<div class="dash"></div><div class="tot"><span>TOTAL</span><b>${then:.2f}</b><b>${now:.2f}</b></div>
<div class="stamp" style="--c:{stamp}">{ch:+.0f}% SINCE 2020</div></div>
<div class="pay" style="--p:{DOWN_GREEN if pch >= ch else UP_RED}">Average hourly pay: ${pay0:.2f} → ${pay1:.2f} <em>({pch:+.0f}%)</em></div>'''
    html = L._page(body.replace("{hl}", f"<em>Receipt</em>"), False, f"BLS average prices & hourly earnings, {month:%b %Y}")
    img = _render(out_dir, "receipt", html)
    key = f"{month:%Y-%m}-pic-receipt"
    biggest = max(rows, key=lambda r: _pct(r[2], r[1]))
    caption = with_question(
        f"The same 8 grocery items cost ${then:.2f} in January 2020. In {month:%B %Y}: ${now:.2f} 🧾 "
        f"That's {'up' if up else 'down'} {abs(ch):.0f}%. Average hourly pay is {'up' if pch >= 0 else 'down'} {abs(pch):.0f}% over the same stretch.\n\n"
        + "\n".join(f"• {n.capitalize()}: ${a:.2f} → ${b:.2f} ({_pct(b, a):+.0f}%)" for n, a, b in rows)
        + f"\n\nBiggest jump: {biggest[0].split(',')[0].lower()}, {_pct(biggest[2], biggest[1]):+.0f}%.",
        "prices", key, item=biggest[0].split(",")[0].lower())
    caption += (f"\n\n📌 Save this and check it against your own receipt. 📤 Send it to whoever does the grocery run."
                f"\n\nSource: U.S. Bureau of Labor Statistics, average retail prices (U.S. city average) and average "
                f"hourly earnings of all private employees, not seasonally adjusted.\n{DISCLAIMER}\n#groceryprices {TAGS}")
    return _post(key, [img], caption, rep)


# ---------------------------------------------------------------- the monthly cheat sheet carousel

def _cover(month, stats):
    cards = "".join(f'''<div class="cd"><div class="k">{escape(k)}</div><div class="v" style="color:{c}">{escape(v)}</div>
<div class="n">{escape(n)}</div></div>''' for k, v, n, c in stats)
    css = """<style>
.pill{align-self:center;background:#1F2937;color:#fff;font-family:"Baloo 2";font-weight:800;font-size:34px;padding:6px 30px;border-radius:999px;margin-bottom:26px}
.cds{display:flex;flex-direction:column;gap:22px;margin-top:40px}
.cd{background:#fff;border-radius:26px;padding:22px 36px;box-shadow:0 6px 0 rgba(0,0,0,.06);display:grid;
    grid-template-columns:260px 1fr;grid-template-rows:auto auto;align-items:center}
.k{font-family:"Baloo 2";font-weight:800;font-size:44px;grid-row:1/3}
.v{font-family:"Baloo 2";font-weight:800;font-size:84px;line-height:1;text-align:right}
.n{font-size:24px;font-weight:700;color:#6B7280;text-align:right}
.sw{margin-top:auto;display:flex;align-items:center;justify-content:space-between;font-family:"Baloo 2";font-weight:800;font-size:46px;color:#1F2937}
</style>"""
    body = f'''{css}<div class="pill">{month:%B %Y} cheat sheet</div>
<div class="t" style="--hl:{BLUE}">Your Money<br><em>This Month</em></div>
<div class="cds">{cards}</div><div class="sw"><span>Swipe for the charts →</span>{mascot_svg(150)}</div>'''
    return L._page(body, False, "BLS · Freddie Mac")


def _outro():
    body = f'''<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:30px">
{mascot_svg(330)}<div class="t" style="--hl:{DOWN_GREEN}">Save This for Your <em>Budget</em></div>
<div class="s" style="font-size:38px">New numbers every month. Follow @paycheck_math so you don't miss them.</div></div>'''
    return L._page(body, False, "BLS · Freddie Mac")


def _three_years(sid, end):
    start = date(end.year - 3, end.month, 1)
    return [p for p in D.series(sid) if p[0] >= start]


def cheatsheet(out_dir, month, rep):
    gas, mort = "APU000074714", "MORTGAGE30"
    D.check_series(rep, [sid for sid, _ in RELEASE_ROWS] + [PAY, mort])
    for sid, name in RELEASE_ROWS:
        rep.require(D.latest(sid)[0] == month, f"{name}: same month as the CPI release", f"latest {D.latest(sid)[0]}")
    cpi = _yoy(rep, CPI)
    pay_m = D.latest(PAY)[0]
    pay = _yoy(rep, PAY)
    (mw, mr), mya = D.latest(mort), D.year_ago_checked(rep, mort)
    g_now, g_ya = D.latest(gas)[1], D.year_ago_checked(rep, gas)
    red_if = lambda bad: UP_RED if bad else DOWN_GREEN
    slides = [_cover(month, [
        ("Prices", f"{cpi:+.1f}%", f"vs. a year ago ({month:%b})", red_if(cpi > pay)),
        ("Your pay", f"{pay:+.1f}%", f"vs. a year ago ({pay_m:%b}) · {'behind' if pay < cpi else 'ahead of'} prices", red_if(pay < cpi)),
        ("Mortgage", f"{mr:.2f}%", f"30-yr fixed, week of {mw:%b} {mw.day}", red_if(mr > mya[1])),
        ("Gas", f"${g_now:.2f}", f"per gallon, was ${g_ya[1]:.2f} a year ago", red_if(g_now > g_ya[1]))])]
    # 2: what got pricier (same rows and colors as the release-day Reel)
    yoy = [(sid, n, _yoy(rep, sid)) for sid, n in RELEASE_ROWS]
    items = [{"label": n, "sub": "vs. a year ago", "value": max(abs(v), 0.1), "icon": ICON[n],
              "value_label": f"{v:+.0f}%" if abs(v) >= 10 else f"{v:+.1f}%", "color": red_if(v > 0)} for sid, n, v in yoy]
    slides.append(L.bars("What Got {hl}?", "Pricier" if cpi >= 0 else "Cheaper", f"{month:%B %Y} vs. a year ago",
                         items, f"BLS CPI & average prices, {month:%b %Y}", tall=False, hl_color=red_if(cpi >= 0)))
    # 3: pay vs prices since January 2020
    names = [(PAY, "Your pay"), (CPI, "Overall prices"), ("CUUR0000SEHA", "Rent"), ("CUUR0000SAF11", "Groceries"), (gas, "Gas")]
    since = [(n, _pct(_at(rep, sid, month, n), _at(rep, sid, BASE, n))) for sid, n in names]
    p20 = since[0][1]
    palette = ["#22C55E", "#A855F7", "#3B82F6", "#F97316", "#EF4444"]
    items = [{"label": n, "sub": "since 2020", "value": max(v, 0.1), "icon": ICON[n], "value_label": f"{v:+.0f}%",
              "color": palette[i]} for i, (n, v) in enumerate(since)]
    slides.append(L.bars("Your Pay vs. {hl}", "Prices", f"Change from January 2020 to {month:%B %Y}", items,
                         f"BLS, {month:%b %Y}", tall=False, hl_color=UP_RED))
    # 4-5: mortgage rate and gas, last 3 years
    for sid, title, word, fmt, ya, end in ((mort, "Mortgage", "Rates", lambda v: f"{v:.2f}%", mya, mw),
                                          (gas, "Gas", "Prices", lambda v: f"${v:.2f}", g_ya, month)):
        pts = _three_years(sid, end)
        rep.require(len(pts) >= 30, f"{title} {word}: 3-year history", f"only {len(pts)} points")
        mi = min(range(len(pts)), key=lambda k: abs((pts[k][0] - ya[0]).days))
        up = pts[-1][1] > ya[1]
        slides.append(L.line(f"{title} {{hl}}", word, "Last 3 years · U.S. average · dot = a year ago", pts, fmt,
                             "Freddie Mac PMMS" if sid == mort else f"BLS, {month:%b %Y}", color=red_if(up),
                             marker=(mi, f"a year ago {fmt(ya[1])}"), tall=False, hl_color=BLUE))
    slides.append(_outro())
    images = [_render(out_dir, f"cheatsheet_{k + 1}", h) for k, h in enumerate(slides)]
    key = f"{month:%Y-%m}-pic-cheatsheet"
    caption = with_question(
        f"Your money this month, in one swipe 👉 ({month:%B %Y} data)\n\n"
        f"{'🔴' if cpi > pay else '🟢'} Prices: {cpi:+.1f}% vs. a year ago\n"
        f"{'🟢' if pay >= cpi else '🔴'} Average hourly pay: {pay:+.1f}% vs. a year ago ({pay_m:%B})\n"
        f"🏠 30-year mortgage rate: {mr:.2f}% (week of {mw:%b} {mw.day}; {mr - mya[1]:+.2f} vs. a year ago)\n"
        f"⛽ Gas: ${g_now:.2f}/gallon (was ${g_ya[1]:.2f})\n\n"
        f"Since January 2020, average pay is up {p20:.0f}% and overall prices are up {since[1][1]:.0f}%.",
        "paycheck", key)
    caption += (f"\n\n📌 Save this for your next budget check. 📤 Send it to someone who'd want the numbers."
                f"\n\nSource: U.S. Bureau of Labor Statistics (CPI, average prices, average hourly earnings, not seasonally "
                f"adjusted) and Freddie Mac Primary Mortgage Market Survey.\n{DISCLAIMER}\n#budget {TAGS}")
    return _post(key, images, caption, rep)


# ---------------------------------------------------------------- comparisons

FLAGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "flags")
WARM_TO_COOL = ["#EF4444", "#F97316", "#F59E0B", "#EAB308", "#14B8A6", "#16A34A"]   # priciest red → cheapest green


def _flag(code):
    """Country flag as a data URI (flagcdn.com, public-domain flag images), cached in data/flags."""
    path = os.path.join(FLAGS, f"{code}.png")
    try:
        if not os.path.exists(path):
            png = D._plain_get(f"https://flagcdn.com/w320/{code}.png")
            if not png.startswith(b"\x89PNG"):
                raise ValueError("not a PNG")
            os.makedirs(FLAGS, exist_ok=True)
            open(path, "wb").write(png)
        return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()
    except Exception as e:
        print(f"  ! flag {code}: {e}")
        return None


def _prices(rep, month, ids):
    """Checked, FRED-confirmed prices for `month`: [(sid, now, year_ago)]."""
    D.check_series(rep, ids)
    for sid in ids:
        rep.require(D.latest(sid)[0] == month, f"{D.SERIES[sid][0]}: same month as the CPI release", f"latest {D.latest(sid)[0]}")
    D.fred_check(rep, ids, month)
    return [(sid, D.latest(sid)[1], D.year_ago_checked(rep, sid)[1]) for sid in ids]


PROTEINS = [("APU0000703511", "Round steak", "steak"), ("APU0000703112", "Ground beef", "beef"), ("APU0000704111", "Bacon", "bacon"),
            ("APU0000FD3101", "Pork chops", "pork"), ("APU0000FF1101", "Chicken breast", "breast"),
            ("APU0000706111", "Whole chicken", "chicken")]


def protein(out_dir, month, rep):
    meta = {sid: (n, ic) for sid, n, ic in PROTEINS}
    got = sorted(_prices(rep, month, [sid for sid, _, _ in PROTEINS]), key=lambda r: -r[1])
    rows = [{"label": meta[sid][0], "sub": f"{_pct(v, ya):+.0f}% vs. last year", "value": v, "value_label": f"${v:.2f}",
             "icon": meta[sid][1], "color": WARM_TO_COOL[k]}
            for k, (sid, v, ya) in enumerate(got)]
    hi, lo = got[0], got[-1]
    ratio = hi[1] / lo[1]
    html = L.hbars("Price Per {hl}", "Pound", f"Meat at the grocery store · U.S. average, {month:%B %Y}", rows,
                   f"BLS average prices, {month:%b %Y} (checked vs. FRED)", hl_color="#F97316",
                   note=f"{meta[hi[0]][0]} costs {ratio:.1f}x as much as {meta[lo[0]][0].lower()}")
    key = f"{month:%Y-%m}-pic-protein"
    caption = with_question(
        f"Price per pound at the grocery store, {month:%B %Y} 🛒\n\n"
        + "\n".join(f"• {meta[sid][0]}: ${v:.2f}/lb ({_pct(v, ya):+.0f}% vs. a year ago)" for sid, v, ya in got)
        + f"\n\n{meta[hi[0]][0]} costs {ratio:.1f}x as much as {meta[lo[0]][0].lower()} per pound.",
        "prices", key, item=meta[hi[0]][0].lower())
    caption += (f"\n\n📌 Save this for your next grocery run. 📤 Send it to the person who meal-preps."
                f"\n\nSource: U.S. Bureau of Labor Statistics average retail prices, U.S. city average, {month:%B %Y}; "
                f"every price matched against the St. Louis Fed's FRED database.\n{DISCLAIMER}\n#mealprep {TAGS}")
    return _post(key, [_render(out_dir, "protein", html)], caption, rep)


REGIONS = [("APU040074714", "West", "W", "incl. CA, AZ, WA"),
           ("APU010074714", "Northeast", "NE", "incl. NY, PA, MA"),
           ("APU020074714", "Midwest", "MW", "incl. IL, OH, MI"),
           ("APU030074714", "South", "S", "incl. TX, FL, GA")]
US_GAS = "APU000074714"


def gas_regions(out_dir, month, rep):
    meta = {sid: (n, chip, sub) for sid, n, chip, sub in REGIONS}
    got = _prices(rep, month, [sid for sid, *_ in REGIONS] + [US_GAS])
    us = next(r for r in got if r[0] == US_GAS)
    regions = sorted([r for r in got if r[0] != US_GAS], key=lambda r: -r[1])
    rep.require(regions[-1][1] <= us[1] <= regions[0][1], "U.S. average sits between the regions",
                f"U.S. {us[1]} vs regions {regions[-1][1]}-{regions[0][1]}")
    pal = ["#EF4444", "#F97316", "#EAB308", "#22C55E"]
    rows = [{"label": meta[sid][0], "sub": meta[sid][2], "value": v, "value_label": f"${v:.2f}", "chip": meta[sid][1],
             "color": pal[k]} for k, (sid, v, ya) in enumerate(regions)]
    rows.insert(next(k for k, r in enumerate(rows) if r["value"] < us[1]),
                {"label": "U.S. average", "sub": "all urban areas", "value": us[1], "value_label": f"${us[1]:.2f}",
                 "chip": "US", "color": BLUE, "mark": True})
    gap = regions[0][1] - regions[-1][1]
    html = L.hbars("Gas Prices by {hl}", "Region", f"Regular unleaded, per gallon · {month:%B %Y}", rows,
                   f"BLS average prices, {month:%b %Y} (checked vs. FRED)", hl_color=BLUE,
                   note=f"A 15-gallon fill-up costs ${gap * 15:.0f} more in the {meta[regions[0][0]][0]} than the {meta[regions[-1][0]][0]}")
    key = f"{month:%Y-%m}-pic-gas_regions"
    caption = with_question(
        f"What a gallon of regular costs depends a lot on where you live ⛽ ({month:%B %Y})\n\n"
        + "\n".join(f"• {meta[sid][0]}: ${v:.2f} (was ${ya:.2f} a year ago)" for sid, v, ya in regions)
        + f"\n• U.S. average: ${us[1]:.2f} (was ${us[2]:.2f})"
        + f"\n\nA 15-gallon fill-up: ${regions[0][1] * 15:.0f} in the {meta[regions[0][0]][0]} vs. "
          f"${regions[-1][1] * 15:.0f} in the {meta[regions[-1][0]][0]}.",
        "prices", key, item="gas")
    caption += (f"\n\n📤 Send this to a friend in the {meta[regions[0][0]][0]}. 📌 Save it for your next road trip."
                f"\n\nSource: U.S. Bureau of Labor Statistics average prices, unleaded regular, by Census region "
                f"(urban areas), {month:%B %Y}; matched against the St. Louis Fed's FRED database.\n{DISCLAIMER}\n#gasprices {TAGS}")
    return _post(key, [_render(out_dir, "gas_regions", html)], caption, rep)


def world_inflation(out_dir, month, rep):
    year, vals = D.world_inflation(rep)
    if year != date.today().year - 1:
        raise NoContent(f"Waiting for {date.today().year - 1} world inflation data (latest full year: {year}).")
    us = vals.get("USA")
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    rows = [{"label": D.COUNTRIES[c][0], "value": max(v, 0), "value_label": f"{v:.1f}%", "img": _flag(D.COUNTRIES[c][1]),
             "chip": D.COUNTRIES[c][0][:2].upper(), "mark": c == "USA",
             "color": BLUE if c == "USA" else (UP_RED if v > us else DOWN_GREEN)} for c, v in order]
    higher = [D.COUNTRIES[c][0] for c, v in order if v > us]
    html = L.hbars("{hl} Inflation", "World", f"How much prices rose in {year}, by country", rows,
                   "IMF (checked vs. World Bank & BLS)", hl_color=BLUE,
                   note="Red = prices rose faster than in the U.S. · Green = slower")
    key = f"{year}-pic-world_inflation"
    caption = with_question(
        f"How much prices rose in {year}, around the world 🌍\n\n"
        + "\n".join(f"{'🔵' if c == 'USA' else ('🔴' if v > us else '🟢')} {D.COUNTRIES[c][0]}: {v:.1f}%" for c, v in order)
        + f"\n\nThe U.S. came in at {us:.1f}%. {len(higher)} of these {len(order) - 1} countries had faster inflation"
        + (f" ({', '.join(higher)})." if higher else "."),
        "prices", key, item="prices")
    caption += (f"\n\n📤 Send this to a friend abroad. 📌 Save it for the next \"prices are crazy\" debate."
                f"\n\nSource: International Monetary Fund, World Economic Outlook (consumer prices, annual average, {year}); "
                f"each figure checked against the World Bank, and the U.S. against BLS.\n{DISCLAIMER}\n#economy {TAGS}")
    return _post(key, [_render(out_dir, "world_inflation", html)], caption, rep)


# (name, key for the latest CPI month, builder). Comparisons are spaced between the monthly staples.
FORMATS = [("cheatsheet", lambda m: f"{m:%Y-%m}-pic-cheatsheet", cheatsheet),
           ("protein", lambda m: f"{m:%Y-%m}-pic-protein", protein),
           ("receipt", lambda m: f"{m:%Y-%m}-pic-receipt", receipt),
           ("gas_regions", lambda m: f"{m:%Y-%m}-pic-gas_regions", gas_regions),
           ("world_inflation", lambda m: f"{date.today().year - 1}-pic-world_inflation", world_inflation)]


def pic_monthly(out_dir, posted=None):
    """Posts the next not-yet-posted picture format for the latest CPI month; idles once all are used."""
    month = D.latest(CPI)[0]
    for name, keyfn, fmt in FORMATS:
        if keyfn(month) in (posted or {}):
            continue
        try:
            return fmt(out_dir, month, C.Report(name))
        except NoContent:
            continue
    raise NoContent(f"All picture posts for {month:%B %Y} are done; waiting for new BLS data.")


BUILDERS = {"pic_monthly": pic_monthly}
