"""Community safety (report §3.8.3): lightweight text screening + report thresholds.

screen(text) → ScreenResult(action, reason)
  reject        – personal contact details, links, harassment or slurs (not saved)
  under_review  – crisis / self-harm content: saved but hidden until reviewed, poster shown SOS
  ok            – published
"""
import random
import re
from dataclasses import dataclass

from ChatbotWebsite.chat.safety import assess_risk

PHONE = re.compile(r"(?:\+?\d[\s-]?){7,}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
LINK = re.compile(r"https?://|www\.|\b[\w-]+\.(com|net|org|np|io|me)\b", re.I)
HARASSMENT = re.compile(
    r"\b(kys|kill yourself|go die|you should die|nobody likes you|you('re| are) (stupid|ugly|worthless|a loser|pathetic))\b",
    re.I)
SLURS = re.compile(r"\b(fuck\w*|bitch\w*|bastard|slut|whore|retard\w*|muji|machikne|randi|kukur ko)\b", re.I)


@dataclass
class ScreenResult:
    action: str          # ok | under_review | reject
    reason: str = ""


def screen(*texts):
    text = " ".join(t or "" for t in texts)
    if EMAIL.search(text) or PHONE.search(text):
        return ScreenResult("reject", "Please don't include phone numbers or email addresses — the community is anonymous.")
    if LINK.search(text):
        return ScreenResult("reject", "Links aren't allowed in the community.")
    if HARASSMENT.search(text) or SLURS.search(text):
        return ScreenResult("reject", "Please keep it kind — harassment and offensive language aren't allowed.")
    if assess_risk(text).level == "high":
        return ScreenResult("under_review", "crisis")
    return ScreenResult("ok")


ADJECTIVES = ["Kind", "Gentle", "Calm", "Brave", "Quiet", "Warm", "Bright", "Steady", "Hopeful", "Soft"]
NOUNS = ["River", "Cloud", "Mountain", "Lotus", "Sparrow", "Moon", "Pine", "Breeze", "Lantern", "Meadow"]


def random_alias(rng=random):
    return f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)} #{rng.randint(100, 999)}"
