"""Rotating debate questions (most posts get one; some deliberately don't)."""
import hashlib

BANK = {
    "prices": [
        "Which of these hurts your budget the most? 👇",
        "What's the one price you've noticed going up the most? 👇",
        "Is it just us, or does {item} feel way higher than this? 👇",
        "What did you cut back on this year? 👇",
    ],
    "mortgage": [
        "Would you buy a house at {rate}%? 👇",
        "Waiting for rates to drop, or buying now? 👇",
        "What rate would get you to buy? Drop a number 👇",
    ],
    "paycheck": [
        "Did your raise keep up with this? 👇",
        "Pay vs. prices: who's winning in your house? 👇",
        "What's harder to afford now than in 2020? 👇",
    ],
    "states": [
        "Where did your state land? 👇",
        "Does your paycheck beat your state's average? 👇",
        "Which state surprised you most? 👇",
    ],
    "minutes": [
        "Which one surprised you most? 👇",
        "How many hours of work is your rent? 👇",
    ],
}


def _fits(q, values):
    try:
        q.format(**values)
        return True
    except (KeyError, IndexError):
        return False


def pick(kind, key, skip_rate=4, **values):
    bank = [q for q in BANK.get(kind, []) if _fits(q, values)]
    if not bank:
        return ""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    if h % skip_rate == 0:
        return ""
    return bank[(h // skip_rate) % len(bank)].format(**values)
