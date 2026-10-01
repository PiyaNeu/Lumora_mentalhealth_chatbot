"""Language detection (report §3.7.6): Devanagari Unicode range + Roman Nepali marker list.

Returns one of:
  "ne"     – Nepali in Devanagari script
  "ne-rom" – Romanized Nepali (Nepali written in Latin letters)
  "en"     – English (default)
"""
import re

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
WORD = re.compile(r"[a-z']+")

# Words that are almost never English: one is enough.
STRONG_MARKERS = {
    "malai", "mero", "meri", "timi", "timro", "tapai", "tapailai", "hajur", "chha", "chhu",
    "chaina", "chhaina", "xaina", "xa", "xu", "garna", "garnu", "garchu", "gardina", "kasto",
    "kina", "kehi", "kei", "thaha", "ramro", "naramro", "dukha", "dukhi", "pir", "chinta",
    "lagyo", "lagcha", "lagchha", "lagxa", "lagdaina", "bhayo", "bhaye", "huncha", "hunchha",
    "hunxa", "sakdina", "sakchu", "dherai", "ekdam", "nindra", "sutna", "padhai", "pariksha",
    "sathi", "aama", "buwa", "babu", "didi", "dai", "bahini", "bhai", "khusi", "eklo", "thakeko",
    "marna", "marchu", "jiuna", "jiudina", "aatmahatya", "atmahatya", "namaste", "dhanyabad",
    "dhanyawad", "maya", "garum", "garau", "bujhena", "bujhchu", "aaja", "bholi", "hijo",
}
# Short or ambiguous tokens that also appear in English chat: need two hits.
WEAK_MARKERS = {"ma", "cha", "ho", "k", "ke", "man", "dar", "ris", "ani", "ta", "ni", "pani", "ali", "hai", "la"}


def detect_language(text):
    if not text:
        return "en"
    if DEVANAGARI.search(text):
        return "ne"
    tokens = WORD.findall(text.lower())
    strong = sum(1 for t in tokens if t in STRONG_MARKERS)
    weak = sum(1 for t in tokens if t in WEAK_MARKERS)
    if strong >= 1 or weak >= 2:
        return "ne-rom"
    return "en"


def is_nepali(lang):
    return lang in ("ne", "ne-rom")
