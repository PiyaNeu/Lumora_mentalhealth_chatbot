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
    r"\b(please |just |someone )?kill me\b",   # not "killing me" ("the deadline is killing me")
    r"\bend(ing)? (my (own )?life|myself)\b",
    r"\bend(ing)? it all\b",
    r"\btake my (own )?life\b",
    r"\b(want|wanna|going|gonna|plan(ning)?|ready|will|should|deserve) to die\b",
    r"\bi (will|should|wanna|want to) (just )?die\b",
    r"\bwish i (was|were) dead\b",
    r"\bbetter off dead\b",
    r"\b(don'?t|do not) want to (live|be alive|exist|wake up)( anymore)?\b",
    r"\bcan'?t live (like this )?any ?more\b",
    r"\bno (reason|will) to (live|go on)\b",
    r"\bdone with (my )?life\b",
    r"\b(hurt|harm|cut|cutting|burn|burning) (myself|my ?self|my (arm|arms|wrist|wrists|body|skin))\b",
    r"\bslit (my )?wrists?\b",
    r"\bself[- ]?harm\w*",
    r"\boverdos\w*",
    r"\b(take|swallow) (all )?(my |the |these )?(pills|tablets|sleeping pills)\b",
    r"\b(drink|take) poison\b|\bpoison myself\b",
    r"\bhang (myself|my ?self)\b",
    r"\bjump (off|from) (a |the )?(bridge|building|roof|terrace|cliff)\b",
    r"\b(kill|hurt|stab|shoot) (him|her|them|someone|somebody|people|my (mom|dad|father|mother|brother|sister))\b",
    r"\bunalive\b",
    # Nepali (Devanagari)
    r"आत्म ?हत्या",
    r"मर्न(ु)? ?मन",
    r"मर्ने (विचार|सोच)",
    r"मर्न चाहन्छु",
    r"मर्छु|मरिदिन्छु|मर्दिन्छु|मरिहाल्छु",
    r"आफू ?लाई (मार|सक|हानि|चोट|काट)",
    r"(जिउन|बाँच्न|बाच्न)(ु)? मन (छैन|लाग्दैन)",
    r"जिउँदिन|बाँच्दिन|बाच्दिन",
    r"(जिन्दगी|जीवन) (सकियो|बेकार|चाहिँदैन|चाहिदैन)",
    r"झुण्डि|झुन्डि",
    r"(विष|बिष|जहर) (खा|पिउ)",
    r"हात काट|नसा काट",
    r"मर्नु (नै )?(राम्रो|ठिक|बेस)",
]

# Romanized Nepali, matched on roman_key(): spelling normalised so that
# mann/man, chhaina/xaina/chaina, aatmahatya/atmahatya, jeevan/jiwan/jiban all match.
ROMAN_HIGH = [
    r"\batma ?hatya",
    r"\bmar(na|nu|ne) (man|ichha|icha|sochchu|sochu|bichar|chahanchu|chahan)",
    r"\bmar(chu|dinchu|idinchu|ihalchu|um|aum)\b",
    r"\b(ma|malai) mar(na|nu|ne)\b",
    r"\bafu ?lai (mar|sak|hani|chot|kat|dukha di)",
    r"\b(hat|nas|nasa) kat",
    r"\b(bachna|banchna|bachnu|jiuna|jiunu|jiun|bachn) (man|icha|ichha) (chaina|lagdaina)",
    r"\b(bachna|banchna|jiuna) (sakdina|chahana|chahanna)",
    r"\b(jiudina|jiundina|bachdina|banchdina)\b",
    r"\b(jindagi|jiban|jibhan|jibn) (sakiyo|sakkiyo|khatam|chaidaina|chahidaina)",
    r"\bjhund(inchu|ina|inu|iyera|chu|ine)",
    r"\b(bis|bish|bikh|jahar) (khanchu|khana|khanu|khaidinchu|piunchu)",
    r"\bsuicide (garchu|garna|garnu|garne)",
    r"\bmarnu (nai |nei )?(ramro|thik|bes|beter)",
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
    r"(जिन्दगी|जीवन) (बेकार|अर्थहीन)",
    r"कोही (वास्ता|माया) गर्दैन",
]

ROMAN_MEDIUM = [
    r"\bnirash",
    r"\b(jindagi|jiban) (bekar|bekkar|arthahin|man pardaina|man pardain)",
    r"\bkasai(le)? (pani )?(maya|basta|wasta) gardaina",
    r"\bkehi (pani )?(kam|kaam) ko chaina",
    r"\bsahana sakdina\b",
]

# Negations that turn a high-risk phrase into a cautious (medium) case
NEGATED = [
    r"\b(not|never|no longer|isn'?t|am not|i'?m not) (suicidal|going to (kill|hurt) myself)\b",
    r"\b(don'?t|do not|never) (want|wanna|plan) to (die|kill myself|hurt myself|end my life)\b",
    r"\bsuicide (prevention|awareness|hotline|helpline|rate|statistics)\b",
    r"\bwhat is (suicide|self[- ]?harm)\b",
    r"मर्न मन छैन",
]
ROMAN_NEGATED = [
    r"\bmar(na|nu) (man|ichha|icha) (chaina|lagdaina)",
]

_HIGH = [re.compile(p, re.IGNORECASE) for p in HIGH_RISK]
_MEDIUM = [re.compile(p, re.IGNORECASE) for p in MEDIUM_RISK]
_NEGATED = [re.compile(p, re.IGNORECASE) for p in NEGATED]
_ROMAN_HIGH = [re.compile(p) for p in ROMAN_HIGH]
_ROMAN_MEDIUM = [re.compile(p) for p in ROMAN_MEDIUM]
_ROMAN_NEGATED = [re.compile(p) for p in ROMAN_NEGATED]


def roman_key(text):
    """Normalise Romanized Nepali spelling so one pattern covers common variants."""
    t = (text or "").lower()
    t = re.sub(r"[^a-z\s]", " ", t)
    for a, b in (("chh", "ch"), ("x", "ch"), ("aa", "a"), ("ee", "i"), ("oo", "u"), ("ph", "f"),
                 ("sh", "s"), ("w", "b"), ("v", "b"), ("z", "j"), ("q", "k")):
        t = t.replace(a, b)
    t = re.sub(r"([a-z])\1+", r"\1", t)      # collapse doubled letters: mann -> man
    return re.sub(r"\s+", " ", t).strip()


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
        roman = roman_key(text)
        hit = _first_match(_HIGH, text) or _first_match(_ROMAN_HIGH, roman)
        if hit:
            if _first_match(_NEGATED, text) or _first_match(_ROMAN_NEGATED, roman):
                if best.level == "none":
                    best = RiskResult("medium", hit)
                continue
            return RiskResult("high", hit)
        hit = _first_match(_MEDIUM, text) or _first_match(_ROMAN_MEDIUM, roman)
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
