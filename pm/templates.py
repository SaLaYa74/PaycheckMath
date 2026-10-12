"""Paycheck Math brand + post templates. Each function returns a full HTML page."""
import re
from html import escape

HANDLE = "@paycheck_math"

BRAND_CSS = """
:root{
  --bg:#0B1410; --panel:#122019; --panel2:#17291F; --line:#23382D;
  --text:#F2F7F4; --muted:#8FA89A; --green:#3DDC84; --red:#FF5A5F; --amber:#E8B84A;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%}
body{background:var(--bg);color:var(--text);font-family:Inter,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;overflow:hidden}
.frame{position:relative;width:100%;height:100%;display:flex;flex-direction:column;padding:64px 72px 56px;
  background:
    radial-gradient(900px 600px at 100% 0%, rgba(61,220,132,.10), transparent 60%),
    radial-gradient(700px 500px at 0% 100%, rgba(232,184,74,.08), transparent 60%),
    var(--bg)}
.frame.story{padding:230px 72px 270px}
.frame.reel{padding:200px 150px 380px 72px}
.grid{position:absolute;inset:0;pointer-events:none;opacity:.35;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
  background-size:54px 54px;mask-image:linear-gradient(180deg,rgba(0,0,0,.6),transparent 45%)}
.cond{font-family:"Barlow Condensed","Arial Narrow",sans-serif}
.top{display:flex;align-items:center;justify-content:space-between;position:relative}
.brand{display:flex;align-items:center;gap:14px;font-weight:700;font-size:26px;letter-spacing:.3px}
.brand svg{width:46px;height:46px}
.pill{font-family:"Barlow Condensed";font-weight:700;font-size:26px;letter-spacing:2px;text-transform:uppercase;
  padding:8px 18px;border:2px solid var(--green);color:var(--green);border-radius:999px}
h1{font-family:"Barlow Condensed";font-weight:800;font-size:104px;line-height:.92;text-transform:uppercase;
  letter-spacing:-.5px;margin-top:44px;position:relative}
h1 em{font-style:normal;color:var(--green)}
.sub{font-size:30px;color:var(--muted);margin-top:18px;line-height:1.35;position:relative}
.body{flex:1;display:flex;flex-direction:column;justify-content:center;position:relative;min-height:0}
.foot{display:flex;justify-content:space-between;align-items:flex-end;font-size:20px;color:var(--muted);
  border-top:2px solid var(--line);padding-top:20px;position:relative;line-height:1.4}
.foot b{color:var(--text);font-weight:600}
.chip{display:inline-flex;align-items:center;justify-content:center;font-family:"Barlow Condensed";font-weight:800;
  color:#fff;border-radius:12px;text-shadow:0 1px 2px rgba(0,0,0,.4)}
.g{color:var(--green)} .r{color:var(--red)} .m{color:var(--muted)}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800'
         '&family=Inter:wght@400;500;600;700;800&display=block" rel="stylesheet">')


def logo_svg(size=46, bg=True):
    rect = '<rect x="2" y="2" width="96" height="96" rx="24" fill="#122019" stroke="#3DDC84" stroke-width="4"/>' if bg else ""
    return f'''<svg width="{size}" height="{size}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">{rect}
  <rect x="16" y="56" width="12" height="24" rx="2" fill="#3DDC84" opacity=".45"/>
  <rect x="32" y="44" width="12" height="36" rx="2" fill="#3DDC84" opacity=".7"/>
  <polygon points="47,50 66,32 85,50" fill="#E8B84A"/>
  <rect x="51" y="50" width="30" height="30" fill="#3DDC84"/><rect x="62" y="62" width="8" height="18" fill="#0B1410"/>
  <line x1="14" y1="82" x2="86" y2="82" stroke="#F2F7F4" stroke-width="3" stroke-linecap="round"/></svg>'''


def mascot_svg(size=64):
    """Penny the squirrel: rising-chart tail, analyst glasses, gold coin."""
    return f'''<svg width="{size}" height="{size}" viewBox="14 16 186 186" xmlns="http://www.w3.org/2000/svg">
  <path d="M150 170 C190 150 196 96 170 70 C150 50 128 62 136 84" fill="none" stroke="#B5652B" stroke-width="26" stroke-linecap="round"/>
  <polyline points="128,150 146,128 160,138 182,104" fill="none" stroke="#3DDC84" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="190,92 172,99 186,113" fill="#3DDC84"/>
  <polygon points="52,40 72,82 40,84" fill="#C8743A"/><polygon points="54,52 66,78 46,80" fill="#7A3E18"/>
  <polygon points="128,40 108,82 140,84" fill="#C8743A"/><polygon points="126,52 114,78 134,80" fill="#7A3E18"/>
  <ellipse cx="90" cy="112" rx="56" ry="50" fill="#C8743A"/><ellipse cx="90" cy="132" rx="34" ry="26" fill="#F4E3CF"/>
  <circle cx="68" cy="106" r="15" fill="rgba(255,255,255,.18)" stroke="#0B1410" stroke-width="5"/>
  <circle cx="112" cy="106" r="15" fill="rgba(255,255,255,.18)" stroke="#0B1410" stroke-width="5"/>
  <line x1="83" y1="104" x2="97" y2="104" stroke="#0B1410" stroke-width="5"/>
  <circle cx="68" cy="107" r="5" fill="#0B1410"/><circle cx="112" cy="107" r="5" fill="#0B1410"/>
  <ellipse cx="90" cy="124" rx="7" ry="5" fill="#0B1410"/>
  <rect x="84" y="134" width="12" height="10" rx="2" fill="#fff" stroke="#0B1410" stroke-width="2"/>
  <circle cx="44" cy="166" r="20" fill="#E8B84A" stroke="#0B1410" stroke-width="4"/>
  <text x="44" y="174" text-anchor="middle" font-family="Arial Black,Arial" font-weight="900" font-size="22" fill="#0B1410">$</text></svg>'''


def page(inner, size="feed", tag="", source="", note=""):
    frame_cls = {"story": "frame story", "reel": "frame reel"}.get(size, "frame")
    note_html = f"<div>{note}</div>" if note else ""
    return f'''<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{BRAND_CSS}</style></head>
<body><div class="{frame_cls}"><div class="grid"></div>
<div class="top"><div class="brand">{logo_svg()}<span>{HANDLE}</span></div>
<div style="display:flex;align-items:center;gap:16px">{f'<div class="pill">{escape(tag)}</div>' if tag else ''}{mascot_svg(68)}</div></div>
{inner}
<div class="foot"><div>{note_html}<div>Data: <b>{escape(source)}</b></div></div><div style="text-align:right">Official data · not financial advice</div></div>
</div></body></html>'''


def chip(abbr, color, size=64, font=30):
    return f'<span class="chip" style="background:{color};width:{size}px;height:{size}px;font-size:{font}px">{escape(abbr)}</span>'


# ---------------- templates ----------------

def profile_pic():
    """Icon-only mark sized to survive Instagram's circular crop."""
    return f'''<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{BRAND_CSS}
body{{display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 50% 45%, #16264a 0%, #0A0F1C 68%)}}
</style></head><body>{logo_svg(700, bg=False)}</body></html>'''


def wordmark():
    """Logo + wordmark for banners, TikTok/X headers, watermark use."""
    return f'''<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{BRAND_CSS}
body{{display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 50% 40%, #13213b 0%, #0A0F1C 70%)}}
.wrap{{display:flex;flex-direction:column;align-items:center;gap:26px}}
.word{{font-family:"Barlow Condensed";font-weight:800;font-size:150px;line-height:.85;text-align:center;letter-spacing:1px}}
</style></head><body><div class="wrap">{logo_svg(440, bg=False)}
<div class="word">SHARP<span class="g">CHARTS</span></div></div></body></html>'''


def intro_post(size="feed"):
    items = [
        ("ATS + O/U trends", "Who's covering, who isn't, and by how much"),
        ("League splits", "Favorites vs. dogs, home vs. away, overs vs. unders"),
        ("Matchup cards", "Every big game, broken down before kickoff"),
        ("Weekly receipts", "We track how our highlighted trends actually hit"),
    ]
    rows = "".join(f'''<div style="display:flex;gap:26px;align-items:flex-start;padding:26px 0;border-bottom:2px solid var(--line)">
      <div class="cond g" style="font-size:54px;font-weight:800;width:70px">0{i+1}</div>
      <div><div style="font-size:38px;font-weight:700">{t}</div><div class="m" style="font-size:27px;margin-top:6px">{d}</div></div></div>'''
                   for i, (t, d) in enumerate(items))
    inner = f'''<h1>Data over<br><em>hunches.</em></h1>
<div class="sub">Clean, verified betting stats &amp; trends. No locks, no hype, just numbers.</div>
<div class="body">{rows}</div>'''
    return page(inner, size, tag="Welcome", source="nflverse · ESPN · verified before posting",
                note="Follow for daily NFL · NBA · MLB charts")


def _head(title_html, subtitle, hook=None):
    if not hook:
        return f'<h1>{title_html}</h1><div class="sub">{subtitle}</div>'
    if not title_html:
        em = ' style="color:var(--red)"' if len(hook) > 2 and hook[2] == "red" else ""
        return f'<h1 style="font-size:96px;line-height:.93;margin-top:30px">{escape(hook[0])}<br><em{em}>{escape(hook[1])}</em></h1>'
    plain = re.sub(r"<[^>]+>", " ", title_html).replace("&amp;", "&")
    plain = escape(re.sub(r"\s+", " ", plain).strip())
    em = ' style="color:var(--red)"' if len(hook) > 2 and hook[2] == "red" else ""
    return (f'<h1 style="font-size:96px;line-height:.93;margin-top:30px">{escape(hook[0])}<br><em{em}>{escape(hook[1])}</em></h1>'
            f'<div class="sub" style="font-size:30px;margin-top:14px"><b style="color:var(--text)">{plain}</b> · {subtitle}</div>')


def big_stat(title_html, subtitle, number, number_label, context_rows, tag, source, size="feed", color="var(--green)", p=1.0, hook=None):
    ctx = "".join(f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:22px 0;border-bottom:2px solid var(--line);font-size:32px">
       <span class="m">{escape(k)}</span><span class="cond" style="font-size:46px;font-weight:700">{v}</span></div>''' for k, v in context_rows)
    inner = f'''{_head(title_html, subtitle, hook)}
<div class="body"><div style="text-align:center;padding:10px 0 30px">
  <div class="cond" style="font-size:300px;font-weight:800;line-height:.9;color:{color};text-shadow:0 0 60px rgba(61,220,132,.25);opacity:{min(1, p * 1.4):.2f};transform:scale({0.55 + 0.45 * p:.3f})">{number}</div>
  <div style="font-size:32px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin-top:8px">{number_label}</div></div>
  <div>{ctx}</div></div>'''
    return page(inner, size, tag=tag, source=source)


def bar_ranking(title_html, subtitle, rows, tag, source, size="feed", note="", scale=None, diverging=True, p=1.0, hook=None,
                glance=False, invert=False):
    """invert=True: positive values are bad (prices going up) and show red."""
    """rows: list of dict(abbr,color,name,value,value_label,record). Diverging bars around 0,
    or left-anchored bars when diverging=False (all-positive data like usage share)."""
    scale = scale or max(abs(r["value"]) for r in rows) or 1
    row_h = 104 if glance else {"feed": 66, "story": 80, "reel": 82}.get(size, 66)
    name_px, detail_px, value_px, chip_px = (36, 22, 54, 66) if glance else (27, 20, 38, 54)
    html_rows = []
    for r in rows:
        pct = abs(r["value"]) / scale * (50 if diverging else 100) * p
        pos = r["value"] >= 0
        good = r["good"] if r.get("good") is not None else (pos != invert)
        grad = ("rgba(61,220,132,.55),var(--green)" if good else "rgba(255,90,95,.55),var(--red)")
        if not diverging:
            pct = min(pct, 100)
        left = "50%" if diverging else "0"
        bar_style = (f"left:{left};width:{pct}%;background:linear-gradient(90deg,{grad})" if pos else
                     f"right:50%;width:{pct}%;background:linear-gradient(270deg,{grad})")
        html_rows.append(f'''<div style="display:flex;align-items:center;gap:18px;height:{row_h}px">
  {chip(r["abbr"], r["color"], chip_px, int(chip_px * .46))}
  <div style="width:{330 if glance else 250}px"><div style="font-size:{name_px}px;font-weight:700;line-height:1.1">{escape(r["name"])}</div>
     <div class="m" style="font-size:{detail_px}px">{escape(r.get("record",""))}</div></div>
  <div style="flex:1;position:relative;height:{44 if glance else 30}px;background:var(--panel);border-radius:8px">
     {'<div style="position:absolute;top:-6px;bottom:-6px;left:50%;width:2px;background:var(--line)"></div>' if diverging else ''}
     <div style="position:absolute;top:0;bottom:0;border-radius:6px;{bar_style}"></div></div>
  <div class="cond {'g' if good else 'r'}" style="width:{170 if glance else 110}px;white-space:nowrap;text-align:right;font-size:{value_px}px;font-weight:800;opacity:{min(1, p * 1.25):.2f}">{escape(r["value_label"])}</div></div>''')
    inner = f'''{_head(title_html, subtitle, hook)}
<div class="body" style="gap:2px">{''.join(html_rows)}</div>'''
    return page(inner, size, tag=tag, source=source, note=note)


def splits(title_html, subtitle, items, tag, source, size="feed", note=""):
    """items: list of dict(label, left=(name,count), right=(name,count))."""
    blocks = []
    pad = 14 if size == "feed" else 30
    for it in items:
        (ln, lc), (rn, rc) = it["left"], it["right"]
        tot = lc + rc or 1
        lp = round(lc / tot * 100)
        lead_left = lc >= rc
        blocks.append(f'''<div style="padding:{pad}px 0;border-bottom:2px solid var(--line)">
  <div class="m" style="font-size:24px;letter-spacing:3px;text-transform:uppercase;font-weight:600;margin-bottom:6px">{escape(it["label"])}</div>
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
    <div><span class="cond" style="font-size:54px;font-weight:800;{'color:var(--green)' if lead_left else ''}">{lc}</span>
         <span style="font-size:28px;font-weight:600;margin-left:10px">{escape(ln)}</span></div>
    <div><span style="font-size:28px;font-weight:600;margin-right:10px">{escape(rn)}</span>
         <span class="cond" style="font-size:54px;font-weight:800;{'' if lead_left else 'color:var(--green)'}">{rc}</span></div></div>
  <div style="display:flex;height:22px;border-radius:999px;overflow:hidden;background:var(--panel)">
    <div style="width:{lp}%;background:{'var(--green)' if lead_left else '#3A4A6B'}"></div>
    <div style="flex:1;background:{'#3A4A6B' if lead_left else 'var(--green)'}"></div></div>
  <div style="display:flex;justify-content:space-between;font-size:21px;margin-top:6px" class="m"><span>{lp}%</span><span>{100-lp}%</span></div></div>''')
    inner = f'''<h1>{title_html}</h1><div class="sub">{subtitle}</div>
<div class="body">{''.join(blocks)}</div>'''
    return page(inner, size, tag=tag, source=source, note=note)


def matchup(away, home, line_info, stat_rows, tag, source, size="feed", note=""):
    """away/home: dict(abbr,name,color). line_info: list of (label, value). stat_rows: (label, away_val, home_val, better)."""
    def side(t, label):
        return f'''<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:14px">
  {chip(t["abbr"], t["color"], 170, 72)}
  <div class="cond" style="font-size:52px;font-weight:800;text-transform:uppercase">{escape(t["name"])}</div>
  <div class="m" style="font-size:22px;letter-spacing:3px;text-transform:uppercase">{label}</div></div>'''
    lines = "".join(f'''<div style="flex:1;text-align:center;padding:18px 8px">
   <div class="m" style="font-size:20px;letter-spacing:2px;text-transform:uppercase">{escape(k)}</div>
   <div class="cond" style="font-size:50px;font-weight:800;margin-top:4px">{escape(v)}</div></div>''' for k, v in line_info)
    rows = "".join(f'''<div style="display:flex;align-items:center;padding:16px 0;border-bottom:2px solid var(--line)">
   <div class="cond" style="flex:1;text-align:left;font-size:44px;font-weight:800;{'color:var(--green)' if b=='away' else ''}">{escape(a)}</div>
   <div class="m" style="flex:1.3;text-align:center;font-size:22px;letter-spacing:2px;text-transform:uppercase;font-weight:600">{escape(lbl)}</div>
   <div class="cond" style="flex:1;text-align:right;font-size:44px;font-weight:800;{'color:var(--green)' if b=='home' else ''}">{escape(h)}</div></div>'''
                   for lbl, a, h, b in stat_rows)
    inner = f'''<div class="body" style="gap:30px">
 <div style="display:flex;align-items:center">{side(away,"Away")}
   <div class="cond m" style="font-size:60px;font-weight:800">@</div>{side(home,"Home")}</div>
 <div style="display:flex;background:var(--panel);border:2px solid var(--line);border-radius:20px">{lines}</div>
 <div>{rows}</div></div>'''
    return page(inner, size, tag=tag, source=source, note=note)


def _rank(team):
    """Small '#7' label when a (abbr, color, rank) tuple carries a ranking."""
    rank = team[2] if len(team) > 2 else None
    return f'<span class="cond g" style="font-size:24px;font-weight:800;width:36px;text-align:right">#{rank}</span>' if rank else (
        '<span style="width:36px"></span>' if len(team) > 2 else "")


def slate(week, rows, tag, source, size="feed", note="", title_html=None,
          subtitle="Every game · spread &amp; total · swipe for breakdowns →"):
    """Every game of the week with spread + total. rows: dict(kick, away, home, spread, total, fav_home)."""
    n = len(rows)
    row_h = min(64, int((760 if size == "feed" else 1060) / max(n, 1)))
    chip_sz = min(46, row_h - 12)
    head = '''<div style="display:flex;align-items:center;padding:0 0 10px;font-size:20px;letter-spacing:2px;text-transform:uppercase;font-weight:600" class="m">
  <div style="width:170px">Kickoff (ET)</div><div style="flex:1">Matchup</div>
  <div style="width:190px;text-align:right">Spread</div><div style="width:120px;text-align:right">Total</div></div>'''
    body = []
    for r in rows:
        body.append(f'''<div style="display:flex;align-items:center;height:{row_h}px;border-top:2px solid var(--line)">
  <div class="m" style="width:170px;font-size:22px;font-weight:600">{escape(r["kick"])}</div>
  <div style="flex:1;display:flex;align-items:center;gap:10px">
    {_rank(r["away"])}{chip(r["away"][0], r["away"][1], chip_sz, int(chip_sz*.42))}<span class="m cond" style="font-size:28px;font-weight:700">@</span>
    {_rank(r["home"])}{chip(r["home"][0], r["home"][1], chip_sz, int(chip_sz*.42))}</div>
  <div class="cond" style="width:190px;text-align:right;font-size:36px;font-weight:800">{escape(r["spread"])}</div>
  <div class="cond g" style="width:120px;text-align:right;font-size:36px;font-weight:800">{escape(r["total"])}</div></div>''')
    title_html = title_html or f"Week {week}<br><em>betting slate</em>"
    inner = f'''<h1 style="font-size:96px">{title_html}</h1>
<div class="sub" style="font-size:26px">{subtitle}</div>
<div class="body" style="justify-content:flex-start;margin-top:26px">{head}{''.join(body)}</div>'''
    return page(inner, size, tag=tag, source=source, note=note)


def game_blocks(title_html, subtitle, games, tag, source, size="feed", note=""):
    """Stacked game cards (any sport). games: dict(kick, headline, total,
    away/home=dict(abbr,color,name,line,detail))."""
    n = max(len(games), 1)
    avail = 700 if size == "feed" else 1000
    block_h = min(240, int(avail / n) - 14)
    big = block_h >= 190
    chip_sz = 62 if big else 50

    def side(t):
        return f'''<div style="display:flex;align-items:center;gap:16px;height:{chip_sz + 8}px">
      {chip(t["abbr"], t["color"], chip_sz, int(chip_sz * .38))}
      <div style="flex:1;min-width:0"><div style="font-size:{28 if big else 24}px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(t["name"])}</div>
        <div class="m" style="font-size:{20 if big else 18}px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(t.get("detail", ""))}</div></div>
      <div class="cond" style="font-size:{44 if big else 38}px;font-weight:800;text-align:right;width:130px">{escape(t.get("line", ""))}</div></div>'''
    blocks = "".join(f'''<div style="background:var(--panel);border:2px solid var(--line);border-radius:20px;padding:{14 if big else 10}px 22px;display:flex;flex-direction:column;justify-content:center;gap:6px;height:{block_h}px">
    <div style="display:flex;justify-content:space-between;font-size:19px;letter-spacing:2px;text-transform:uppercase;font-weight:600">
      <span class="m">{escape(g["kick"])} · <span style="color:var(--text)">O/U {escape(g.get("total", "—"))}</span></span><span class="g">{escape(g.get("headline", ""))}</span></div>
    {side(g["away"])}{side(g["home"])}</div>''' for g in games)
    inner = f'''<h1 style="font-size:92px">{title_html}</h1><div class="sub" style="font-size:26px">{subtitle}</div>
<div class="body" style="justify-content:flex-start;gap:14px;margin-top:24px">{blocks}</div>'''
    return page(inner, size, tag=tag, source=source, note=note)


def reel_hook(line1, line2, tag, p=1.0):
    """Opening Reel frame: the hook, big and centered, with the mascot."""
    inner = f'''<div class="body" style="align-items:center;text-align:center;gap:40px">
  <div style="transform:scale({0.9 + 0.1 * p:.3f});opacity:{min(1, p * 1.5):.2f}">{mascot_svg(260)}</div>
  <h1 style="margin:0;font-size:122px;line-height:.95">{line1}<br><em>{line2}</em></h1>
  <div class="sub" style="font-size:34px">Watch the chart <span class="g">↓</span></div></div>'''
    return page(inner, "reel", tag=tag, source="verified before posting")


def reel_outro(tag):
    """Closing Reel frame: follow call-to-action."""
    inner = f'''<div class="body" style="align-items:center;text-align:center;gap:34px">
  {mascot_svg(340)}
  <h1 style="margin:0;font-size:110px">Follow<br><em>{HANDLE}</em></h1>
  <div class="sub" style="font-size:36px">Your paycheck vs. the real cost of living</div>
  <div class="pill" style="font-size:30px;margin-top:10px">Save this · send it to your group chat</div></div>'''
    return page(inner, "reel", tag=tag, source="nflverse · MLB · ESPN")


def one_stat(hook, number, label, who, color, tag, source, p=1.0, note="Penny's number of the week 🐿️"):
    """One giant number, readable in under a second. who = dict(abbr, color, name)."""
    c = "var(--green)" if color == "green" else "var(--red)"
    glow = "rgba(61,220,132,.30)" if color == "green" else "rgba(255,90,95,.30)"
    inner = f'''{_head("", "", hook) if hook else ""}
<div class="body" style="align-items:center;text-align:center;gap:26px">
  <div style="display:flex;align-items:center;gap:20px;opacity:{min(1, p * 2):.2f}">
    {chip(who["abbr"], who["color"], 84, 36)}
    <div class="cond" style="font-size:64px;font-weight:800;text-transform:uppercase">{escape(who["name"])}</div></div>
  <div class="cond" style="font-size:{int((250 + 170 * p) * min(1, 4.6 / max(len(number), 1)))}px;font-weight:800;line-height:.85;color:{c};text-shadow:0 0 80px {glow}">{escape(number)}</div>
  <div style="font-size:40px;font-weight:700;letter-spacing:4px;text-transform:uppercase;opacity:{min(1, p * 1.5):.2f}">{escape(label)}</div></div>'''
    return page(inner, "reel", tag=tag, source=source, note=note)


def line_chart(hook, pts, fmt, tag, source, color, p=1.0, note="", end_label="", marker=None):
    """One series drawn left→right as the Reel plays. pts=[(date, value)].
    marker=(index, text): a labeled reference point (e.g. 'a year ago') so the hook and the picture agree."""
    W, H, pad_l, pad_r, pad_t, pad_b = 860, 860, 30, 160, 110, 80
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    lo, hi = lo - span * 0.15, hi + span * 0.18
    xs = [pad_l + i * (W - pad_l - pad_r) / (len(pts) - 1) for i in range(len(pts))]
    ys = [pad_t + (hi - v) / (hi - lo) * (H - pad_t - pad_b) for v in vals]
    n = max(2, int(round(p * (len(pts) - 1))) + 1)
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs[:n], ys[:n]))
    c = "#3DDC84" if color == "green" else "#FF5A5F"
    glow = "rgba(61,220,132,.45)" if color == "green" else "rgba(255,90,95,.45)"
    seen, ticks = set(), ""
    for i, (d, _) in enumerate(pts):
        if d.month == 1 and d.year not in seen:
            seen.add(d.year)
            ticks += f'<text x="{xs[i]:.0f}" y="{H - 30}" fill="#8FA89A" font-size="28" font-family="Inter" text-anchor="middle">{d.year}</text>'
    mk = ""
    if marker and marker[0] < n:
        i, text = marker
        mk = (f'<line x1="{xs[i]:.1f}" y1="{ys[i]:.1f}" x2="{xs[i]:.1f}" y2="{H - pad_b}" stroke="#8FA89A" stroke-width="2" stroke-dasharray="6 8"/>'
              f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="12" fill="#F2F7F4"/>'
              f'<text x="{xs[i]:.1f}" y="{ys[i] - 30:.1f}" fill="#F2F7F4" font-size="34" font-weight="700" font-family="Barlow Condensed" '
              f'text-anchor="middle">{escape(text)}</text>')
    end = (f'<circle cx="{xs[n-1]:.1f}" cy="{ys[n-1]:.1f}" r="16" fill="{c}"/>'
           f'<text x="{xs[n-1] + 24:.1f}" y="{ys[n-1] + 18:.1f}" fill="{c}" font-size="64" font-weight="800" '
           f'font-family="Barlow Condensed" opacity="{min(1, p * 1.3):.2f}">{escape(fmt(vals[n-1]))}</text>')
    svg = f'''<svg width="100%" viewBox="0 0 {W} {H}" style="overflow:visible">
  <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - pad_r}" y2="{H - pad_b}" stroke="#23382D" stroke-width="3"/>
  <polyline points="{path}" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"
    style="filter:drop-shadow(0 0 14px {glow})"/>{mk}{end}{ticks}</svg>'''
    inner = f'''{_head("", "", hook)}
<div class="sub" style="font-size:30px;margin-top:14px">{escape(end_label)}</div>
<div class="body" style="justify-content:flex-start;margin-top:10px">{svg}</div>'''
    return page(inner, "reel", tag=tag, source=source, note=note)
