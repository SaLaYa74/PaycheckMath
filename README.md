# Paycheck Math (@paycheckmath)

Your paycheck vs. the real cost of living, in glanceable charts and Reels.

**Data (official, primary sources):** U.S. Bureau of Labor Statistics public API (prices, rent, groceries, gas, wages, CPI) and Freddie Mac's Primary Mortgage Market Survey (30-year rate). Every post passes `pm/checks.py`: data is current, values are plausible, the latest move is realistic, captions cite sources and say "not financial advice". Any failure blocks the post; results are saved as `checks.json` next to each post.

- Calendar: `pm/schedule.py` (live=False = preview only) · runner: `autopost.py` (GitHub Actions, every 15 min)
- Kill switch: repo variable `POSTING_ENABLED` · secrets: `IG_TOKEN`, `GH_PAT`
- Analytics (local only): `python3 insights.py` · save token: `python3 save_token.py`
- Mascot: Penny the squirrel 🐿️
