"""Rule-based guards (report §3.7.4, §3.7.7a): fast, deterministic replies for edge cases.

Checked on the English (translated) text after safety screening and before the
intent model. Returns (guard_name, {lang: reply}) or None.
"""
import random
import re

GREETING = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|yo|namaste|namaskar|good (morning|afternoon|evening)|"
    r"how are you|how r u|sup|what'?s up|hello there|hi there|hey there)[\s!.?]*$",
    re.IGNORECASE,
)
IDK = re.compile(
    r"^\s*(idk|i ?d ?k|i don'?t know|i dont know|i do not know|dunno|not sure|no idea|"
    r"i'?m not sure|nothing|hmm+|meh|whatever)[\s!.?]*$",
    re.IGNORECASE,
)
# Questions about the bot itself, attempts to change its rules, or asks for diagnosis
META = re.compile(
    r"\b(who|what) are you\b|\bare you (a )?(bot|robot|human|real|ai|chatgpt|therapist|doctor)\b|"
    r"\bwhat can you do\b|\bhow do you work\b",
    re.IGNORECASE,
)
UNSAFE_PROMPT = re.compile(
    r"\bignore (all |your |the )?(previous|prior|above) (instructions|rules|prompts?)\b|"
    r"\bsystem prompt\b|\bjailbreak\b|\bdeveloper mode\b|\byou are now\b|\bpretend (to be|you are)\b|"
    r"\bact as (a |an )?(doctor|psychiatrist|therapist)\b",
    re.IGNORECASE,
)
DIAGNOSIS = re.compile(
    r"\bdiagnos\w*|\bdo i have (depression|anxiety|bipolar|adhd|ocd|ptsd|a (mental )?(illness|disorder))\b|"
    r"\b(am i|i am|i'?m) (depressed|bipolar|mentally ill)\b\?|"
    r"\bwhat (medicine|medication|pills?|dose|dosage) should i\b|\bprescri\w*",
    re.IGNORECASE,
)
# Physical health (Lumora is not a medical service): someone is ill, injured or in hospital
MEDICAL_URGENT = re.compile(
    r"\b(unconscious|fainted|passed out|not breathing|stopped breathing|bleeding (a lot|heavily|badly)|"
    r"seizure|having fits|heart attack|stroke|chest pain|choking|severe (burn|bleeding|pain)|"
    r"(had|in|met with) an accident|got hit by (a )?(car|bus|bike|motorbike|truck)|"
    r"snake ?bite|poisoned)\b|बेहोस|बेहोश|रगत धेरै|दुर्घटना|\b(behos|behosh|ragat dherai|durghatana)\b",
    re.IGNORECASE,
)
PHYSICAL_ILLNESS = re.compile(
    r"\b(sick|(is|am|was|feel|feeling|fell|been|very|really|so) ill|unwell|fever|flu|cold and cough|covid|corona|dengue|typhoid|infection|vomit\w*|diarrh\w*|"
    r"hospital\w*|admitted|surgery|operation|injur\w*|broke (his|her|my|their) \w+|fracture|disease|"
    r"cancer|diagnosed with)\b|बिरामी|ज्वरो|जरो|अस्पताल|\b(birami|jwaro|jaro|aspatal|bimar)\b",
    re.IGNORECASE,
)
# Mental-health uses of the same words stay with the intent model
_MENTAL_CONTEXT = re.compile(r"\b(sick of|sick and tired|mentally ill|homesick|love ?sick|feel(ing)? sick of)\b",
                             re.IGNORECASE)

_WORD = re.compile(r"[a-zA-Zऀ-ॿ]")

REPLIES = {
    "greeting": {
        "en": [
            "Hi, I'm Lumora 💜 I'm here to listen. How are you feeling today?",
            "Hello! It's good to hear from you. What's on your mind right now?",
            "Hey there. I'm glad you stopped by. How has your day been so far?",
        ],
        "ne": [
            "नमस्ते, म लुमोरा 💜 म सुन्न यहाँ छु। आज तपाईंलाई कस्तो महसुस भइरहेको छ?",
            "नमस्ते! तपाईंको मनमा अहिले के छ?",
        ],
    },
    "too_short": {
        "en": [
            "I'm here. Could you tell me a little more about how you're feeling?",
            "Take your time — what would you like to talk about?",
        ],
        "ne": ["म यहाँ छु। तपाईंलाई कस्तो महसुस भइरहेको छ, अलि बढी भन्न सक्नुहुन्छ?"],
    },
    "idk": {
        "en": [
            "That's okay — it's normal not to have the words yet. If you had to pick one word for today, "
            "would it be tired, stressed, sad, or something else?",
            "Not knowing is completely fine. Sometimes it helps to start small: how has your sleep been lately?",
        ],
        "ne": ["ठिकै छ — कहिलेकाहीँ भावना शब्दमा भन्न गाह्रो हुन्छ। आजको लागि एउटा शब्द रोज्नुपर्दा: थकित, तनाव, उदास, वा अरू केही?"],
    },
    "meta": {
        "en": [
            "I'm Lumora, a supportive wellbeing chatbot — not a person, therapist or doctor. "
            "I can listen, share coping ideas, guide you through mindfulness and journaling, and point you to "
            "help when you need it. I can't diagnose anything. What would you like to talk about?",
        ],
        "ne": [
            "म लुमोरा हुँ, एक सहयोगी च्याटबट — मानिस, थेरापिस्ट वा डाक्टर होइन। म सुन्न, सामना गर्ने उपायहरू बताउन "
            "र आवश्यक परे सहयोगतर्फ डोऱ्याउन सक्छु। म रोग पहिचान (डायग्नोसिस) गर्न सक्दिन। के कुरा गर्न चाहनुहुन्छ?",
        ],
    },
    "unsafe_prompt": {
        "en": [
            "I need to stay within my role as a supportive, non-clinical wellbeing companion, so I can't change "
            "how I work. I'm happy to keep talking about how you're feeling, though.",
        ],
        "ne": ["म सहयोगी च्याटबटको भूमिकाभित्रै रहनुपर्छ, त्यसैले म आफ्नो काम गर्ने तरिका बदल्न सक्दिन। तर तपाईंको भावनाबारे कुरा गर्न म तयार छु।"],
    },
    "medical_urgent": {
        "en": [
            "This sounds like it could be a medical emergency. Please call emergency services or get to the "
            "nearest hospital right now, and ask someone nearby to help. If you can, stay with the person and keep "
            "them safe until help arrives. I'm here to talk afterwards.",
        ],
        "ne": [
            "यो आपतकालीन स्वास्थ्य अवस्था जस्तो लाग्छ। कृपया अहिले नै आपतकालीन सेवामा फोन गर्नुहोस् वा नजिकको "
            "अस्पताल जानुहोस्, र नजिकैको कसैलाई सहयोग माग्नुहोस्। सकेसम्म बिरामीको साथमा बस्नुहोस्। पछि कुरा गर्न म यहीँ छु।",
        ],
    },
    "physical_illness": {
        "en": [
            "I'm sorry someone is unwell — that can be really worrying. I can't give medical advice, so for "
            "symptoms like a fever it's best to see a doctor or visit a health post, especially if it's high, "
            "lasts more than a couple of days or gets worse. Rest and fluids usually help in the meantime. "
            "How are you feeling about it?",
            "That sounds stressful. For physical symptoms, a doctor or health post is the right place to get "
            "checked — and if things get worse suddenly, go to the nearest hospital. Caring for someone can be "
            "tiring too. How are you holding up?",
        ],
        "ne": [
            "कोही बिरामी हुनुहुन्छ भन्ने सुनेर दुःख लाग्यो — यसले चिन्ता लाग्न सक्छ। म चिकित्सा सल्लाह दिन सक्दिन, त्यसैले "
            "ज्वरो जस्ता लक्षणका लागि डाक्टर वा स्वास्थ्य चौकीमा देखाउनु राम्रो हुन्छ, विशेषगरी धेरै भए, दुई-तीन दिनभन्दा बढी "
            "रहे वा बिग्रँदै गए। आराम र पानीले बीचमा मद्दत गर्छ। तपाईंलाई यसबारे कस्तो लागिरहेको छ?",
        ],
    },
    "diagnosis": {
        "en": [
            "I can't diagnose or recommend medication — only a qualified professional can do that. "
            "What I can do is help you reflect on what you're experiencing. If you'd like, the PHQ-9 or GAD-7 "
            "self-check gives an indicative (not diagnostic) picture you could share with a doctor. "
            "What has been bothering you most?",
        ],
        "ne": [
            "म रोग पहिचान गर्न वा औषधि सिफारिस गर्न सक्दिन — त्यो योग्य स्वास्थ्यकर्मीले मात्र गर्न सक्नुहुन्छ। "
            "तर तपाईंले के अनुभव गरिरहनुभएको छ भनेर सोच्न म मद्दत गर्न सक्छु। तपाईंलाई सबैभन्दा बढी के कुराले सताइरहेको छ?",
        ],
    },
}


def check_guards(text_en, raw_text=""):
    """Return (guard_name, replies_by_lang) if a guard applies, else None."""
    text = (text_en or "").strip()
    if len(_WORD.findall(raw_text or text)) < 2 and not GREETING.match(text):
        return "too_short", REPLIES["too_short"]
    if UNSAFE_PROMPT.search(text):
        return "unsafe_prompt", REPLIES["unsafe_prompt"]
    raw = raw_text or text
    if MEDICAL_URGENT.search(text) or MEDICAL_URGENT.search(raw):
        return "medical_urgent", REPLIES["medical_urgent"]
    if (PHYSICAL_ILLNESS.search(text) or PHYSICAL_ILLNESS.search(raw)) and not _MENTAL_CONTEXT.search(text):
        return "physical_illness", REPLIES["physical_illness"]
    if DIAGNOSIS.search(text):
        return "diagnosis", REPLIES["diagnosis"]
    if GREETING.match(text):
        return "greeting", REPLIES["greeting"]
    if IDK.match(text):
        return "idk", REPLIES["idk"]
    if META.search(text):
        return "meta", REPLIES["meta"]
    return None


def pick(replies, lang, avoid=None):
    """Choose a reply in the user's language, avoiding an exact repeat of the last reply."""
    options = replies.get("ne" if lang in ("ne", "ne-rom") else "en") or replies["en"]
    choices = [r for r in options if r != avoid] or options
    return random.choice(choices)
