"""Risk-first safety screening (report §3.7.3, §4.2.4).

Runs on the raw message AND its English translation *before* any other processing.
  high   → SOS response; normal conversation is interrupted (no therapy, no LLM)
  medium → cautious, supportive template that points to SOS resources
  none   → continue down the pipeline

Rule/keyword based, so it errs on the side of caution: false positives are
acceptable, missed crises are not. Negated statements ("I'm not suicidal") are
downgraded to medium rather than ignored.
"""
import re
from dataclasses import dataclass

HIGH_RISK = [
    r"\bsuicid\w*",
    r"\bkill(ing)? my ?self\b",
    r"\bend(ing)? my (own )?life\b",
    r"\bend(ing)? it all\b",
    r"\btake my (own )?life\b",
    r"\b(want|wanna|going|plan(ning)?|ready) to die\b",
    r"\bwish i (was|were) dead\b",
    r"\bbetter off dead\b",
    r"\b(don'?t|do not) want to (live|be alive|exist)( anymore)?\b",
    r"\bno reason to (live|go on)\b",
    r"\b(hurt|harm|cut|cutting|burn) (myself|my ?self|my (arm|wrist|wrists|body))\b",
    r"\bself[- ]?harm\w*",
    r"\boverdos\w*",
    r"\bhang (myself|my ?self)\b",
    r"\bjump (off|from) (a |the )?(bridge|building|roof)\b",
    r"\b(kill|hurt|stab|shoot) (him|her|them|someone|somebody|people|my (mom|dad|father|mother|brother|sister))\b",
    r"\bunalive\b",
    # Nepali (romanized, as typed)
    r"\bmarna (man|mann)\b",
    r"\bmarchu\b",
    r"\bmar(i)?dinchu\b",
    r"\ba+tmahatya\b",
    r"\bjiuna (man|mann) (chaina|chhaina|xaina)\b",
    # Nepali (Devanagari)
    r"आत्महत्या",
    r"मर्न मन",
    r"मर्छु",
    r"मरिदिन्छु",
    r"(जिउन|बाँच्न) मन छैन",
]

MEDIUM_RISK = [
    r"\bhopeless\b",
    r"\bworthless\b",
    r"\b(no|not any) point (in )?(living|life|anything|trying|going on)\b",
    r"\bcan'?t (go on|take (it|this) anymore|do this anymore)\b",
    r"\bgive up on (everything|life|myself)\b",
    r"\bi'?m a burden\b",
    r"\bburden (to|on) (everyone|my family|others)\b",
    r"\bnobody (cares|would (care|notice))\b",
    r"\b(want|wish) (to|i could) disappear\b",
    r"\bempty inside\b",
    r"\bi hate myself\b",
    r"\bnothing matters\b",
    r"\btired of (living|life|everything)\b",
    r"\b(abus(e|ed|ing)|assault(ed)?)\b",
    r"निराश",
    r"\bniraash?\b",
]

# Negations that turn a high-risk phrase into a cautious (medium) case
NEGATED = [
    r"\b(not|never|no longer|isn'?t|am not|i'?m not) (suicidal|going to (kill|hurt) myself)\b",
    r"\b(don'?t|do not|never) (want|wanna|plan) to (die|kill myself|hurt myself|end my life)\b",
    r"\bsuicide (prevention|awareness|hotline|helpline|rate|statistics)\b",
    r"\bwhat is (suicide|self[- ]?harm)\b",
]

_HIGH = [re.compile(p, re.IGNORECASE) for p in HIGH_RISK]
_MEDIUM = [re.compile(p, re.IGNORECASE) for p in MEDIUM_RISK]
_NEGATED = [re.compile(p, re.IGNORECASE) for p in NEGATED]


@dataclass
class RiskResult:
    level: str = "none"   # none | medium | high
    matched: str = ""

    @property
    def is_high(self):
        return self.level == "high"

    @property
    def is_medium(self):
        return self.level == "medium"


def _normalize(text):
    text = (text or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text)


def _first_match(patterns, text):
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0).strip()
    return None


def assess_risk(*texts):
    """Screen one or more versions of a message (raw, translated). Highest level wins."""
    best = RiskResult()
    for raw in texts:
        text = _normalize(raw)
        if not text:
            continue
        hit = _first_match(_HIGH, text)
        if hit:
            if _first_match(_NEGATED, text):
                if best.level == "none":
                    best = RiskResult("medium", hit)
                continue
            return RiskResult("high", hit)
        hit = _first_match(_MEDIUM, text)
        if hit and best.level == "none":
            best = RiskResult("medium", hit)
    return best


SOS_REPLY = {
    "en": (
        "I'm really sorry you're feeling this way, and I'm glad you told me. "
        "Your safety matters most right now, and this is more than I can help with as a chatbot.\n\n"
        "Please reach out for immediate support: open the SOS page for Nepal helplines, "
        "or contact local emergency services now. If you can, tell someone you trust "
        "and stay near them.\n\n"
        "If you are in immediate danger, please call emergency services right away. You don't have to go through this alone."
    ),
    "ne": (
        "तपाईंलाई यस्तो महसुस भइरहेकोमा मलाई साँच्चै दुःख लाग्यो, र मलाई भन्नुभएकोमा धन्यवाद। "
        "अहिले तपाईंको सुरक्षा सबैभन्दा महत्त्वपूर्ण छ।\n\n"
        "कृपया तुरुन्त सहयोग लिनुहोस्: नेपालका हेल्पलाइनहरूको लागि SOS पेज खोल्नुहोस्, "
        "वा स्थानीय आपतकालीन सेवामा सम्पर्क गर्नुहोस्। सम्भव भए आफूले विश्वास गर्ने कसैलाई भन्नुहोस् र उहाँको नजिक बस्नुहोस्।\n\n"
        "तपाईं एक्लै हुनुहुन्न।"
    ),
}

MEDIUM_REPLY = {
    "en": (
        "That sounds really heavy, and I'm sorry you're carrying it. Thank you for sharing it with me. "
        "You don't have to fix everything right now — one small step is enough, like slowing your breathing "
        "or reaching out to someone you trust.\n\n"
        "If these feelings get stronger or you start thinking about harming yourself, please use the SOS page "
        "to reach a helpline straight away.\n\n"
        "Would you like to tell me a little more about what's been happening?"
    ),
    "ne": (
        "यो साँच्चै गाह्रो सुनिन्छ, र तपाईंले यो बोकिरहनुभएकोमा मलाई दुःख लाग्यो। मसँग भन्नुभएकोमा धन्यवाद। "
        "अहिले सबै कुरा मिलाउनु पर्दैन — एउटा सानो कदम पुग्छ, जस्तै बिस्तारै सास फेर्नु वा विश्वासिलो व्यक्तिसँग कुरा गर्नु।\n\n"
        "यदि यी भावनाहरू बढ्दै गए वा आफूलाई हानि गर्ने विचार आयो भने, कृपया तुरुन्तै SOS पेजबाट हेल्पलाइनमा सम्पर्क गर्नुहोस्।\n\n"
        "के भइरहेको छ, अलि बढी भन्न चाहनुहुन्छ?"
    ),
}
