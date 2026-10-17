"""Penny's voice: human openers and sign-offs wrapped around the (unchanged) data caption."""
import hashlib

OPENERS = {
    "mortgage_up": ["Not what house hunters wanted to hear 😩", "Mortgage rates went up again. Of course they did 🙃",
                    "If you're house shopping, sit down for this one 🏠", "Rates ticked up. Here's what that costs you 👇"],
    "mortgage_down": ["Finally, a little good news for house hunters 🏠", "Rates came down this week 👀",
                      "Okay, this is a step in the right direction 🙌"],
    "pay_vs": ["Has your paycheck kept up? Let's check the math 🧮", "This is why your money doesn't go as far 😮‍💨",
               "Raises vs. reality. Here's the scoreboard 👇"],
    "groceries": ["Grocery receipt check 🧾", "Some prices are finally calming down. Some... aren't 😬",
                  "Here's what everyday stuff costs now vs. a year ago 🛒"],
    "minutes": ["How long do you have to work to buy this stuff? ⏱️", "Your time = money. Literally. Here's the math 🧮"],
    "gas": ["Gas check ⛽", "Filling up hurts a little more (or less) lately. Here's the number ⛽"],
    "trend_up": ["Yep, it's not just you. This got more expensive 😩", "Price check, and it's not pretty 📈"],
    "trend_down": ["Some actual good news for your wallet 🙌", "Finally, something got cheaper 📉"],
    "pay_trend": ["Paychecks are moving. Here's how much 💵", "Good news (kind of): pay is up 📈"],
}
SIGNOFFS = ["— Penny 🐿️", "Penny, out 🐿️💵", "— Penny (your money-math squirrel) 🐿️"]


def _kind(key, caption):
    k, first = key.lower(), caption.split("\n")[0].lower()
    if "mortgage" in k:
        return "mortgage_up" if "(+" in first else "mortgage_down"
    for part, kind in (("pay_vs", "pay_vs"), ("groceries", "groceries"), ("minutes", "minutes"), ("-gas", "gas")):
        if part in k:
            return kind
    if "trend" in k:
        if "hourly pay" in first or "average hourly pay" in first:
            return "pay_trend"
        return "trend_up" if " up " in first else "trend_down"
    return None


def humanize(key, caption):
    kind = _kind(key, caption)
    if not kind:
        return caption
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    opener = OPENERS[kind][h % len(OPENERS[kind])]
    lines = caption.split("\n")
    cut = next((i for i, l in enumerate(lines) if l.startswith(("Source:", "Data:", "👉"))), len(lines))
    body = lines[:cut]
    while body and not body[-1].strip():
        body.pop()
    if (h >> 8) % 2 == 0:
        body += ["", SIGNOFFS[(h >> 12) % len(SIGNOFFS)]]
    return "\n".join([opener, ""] + body + [""] + lines[cut:]).replace("\n\n\n", "\n\n")
