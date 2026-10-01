"""Humanizer / therapeutic presence layer (report §3.7.5).

Final pass on every non-SOS reply: removes robotic boilerplate, enforces
non-diagnostic wording, softens tone with contractions, avoids doubled empathy
phrases, and keeps the length readable.
"""
import re

MAX_CHARS = 900

ROBOTIC = [
    r"as an ai( language model)?,?\s*",
    r"i am (just )?a (chat)?bot,? (so )?",
    r"my knowledge and understanding are limited by the data that i was trained on\.?\s*",
]

# Sentences that sound like a diagnosis are replaced, not edited
DIAGNOSTIC = re.compile(
    r"\byou (have|are suffering from|suffer from|might have|may have|probably have)\s+"
    r"(clinical |major |severe )?(depression|an? (\w+ )?disorder|bipolar|adhd|ocd|ptsd|schizophrenia|"
    r"a mental illness)\b|"
    r"\byou are (clinically )?(depressed|bipolar|mentally ill)\b|"
    r"\b(i|we) (can )?diagnose\b|\byour diagnosis\b",
    re.IGNORECASE,
)
NON_DIAGNOSTIC = "I can't diagnose anything, but what you're describing sounds genuinely hard."

CONTRACTIONS = [
    (r"\bI am\b", "I'm"), (r"\byou are\b", "you're"), (r"\bdo not\b", "don't"),
    (r"\bit is\b", "it's"), (r"\bcannot\b", "can't"), (r"\bthat is\b", "that's"),
    (r"\bdoes not\b", "doesn't"), (r"\bis not\b", "isn't"), (r"\blet us\b", "let's"),
]

EMPATHY_START = re.compile(r"^(i'?m (so |really )?sorry|that sounds|i hear you|it sounds like|thank you for)",
                           re.IGNORECASE)


def _sentences(text):
    return re.split(r"(?<=[.!?])\s+", text)


def humanize(text, lang="en"):
    if not text:
        return text
    out = text
    for pat in ROBOTIC:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)

    # Non-diagnostic enforcement, sentence by sentence, keeping paragraph breaks
    paragraphs = []
    for para in out.split("\n\n"):
        kept, replaced = [], False
        for s in _sentences(para):
            if DIAGNOSTIC.search(s):
                if not replaced:
                    kept.append(NON_DIAGNOSTIC)
                    replaced = True
            else:
                kept.append(s)
        paragraphs.append(" ".join(kept))
    out = "\n\n".join(p for p in paragraphs if p.strip())

    if lang == "en":
        paras = out.split("\n\n")
        # Opener + response both starting with empathy reads robotic: keep only the first
        sents = _sentences(paras[0])
        if len(sents) > 2 and EMPATHY_START.match(sents[0]) and EMPATHY_START.match(sents[1]):
            paras[0] = " ".join([sents[0]] + sents[2:])
        out = "\n\n".join(paras)
        for pat, rep in CONTRACTIONS:
            out = re.sub(pat, rep, out)
        # Capitalise the first letter of each paragraph
        out = "\n\n".join(p[:1].upper() + p[1:] for p in out.split("\n\n"))

    out = re.sub(r"[ \t]+", " ", out).strip()
    if len(out) > MAX_CHARS:
        cut = out[:MAX_CHARS]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("।"))
        out = cut[: end + 1] if end > 200 else cut.rstrip() + "…"
    return out
