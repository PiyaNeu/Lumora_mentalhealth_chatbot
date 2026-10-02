"""Therapeutic strategy layer — the "brain" (report §3.7.7d, §3.10.3).

Chooses a response style from the user's preferred mode. In "auto" mode the brain
decides from emotional intensity (VADER compound) and the topic of the intent:
  listener  – strong negative emotion / grief / loneliness: validate, little advice
  coach     – practical problems (exams, sleep, focus): small concrete steps
  therapist – relationships, self-worth, guilt, anger: reflect + gentle reframing question
  balanced  – everything else
Then it wraps the core content (intent response) in a style-specific opener and closer.
"""
import random

MODES = ("auto", "listener", "coach", "therapist", "balanced")
MODE_LABELS = {
    "auto": "Auto (Lumora decides)",
    "listener": "Gentle Listener (warm + comforting)",
    "coach": "Calm Coach (step-by-step help)",
    "therapist": "Reflective Therapist (deep understanding)",
    "balanced": "Balanced (mix of both)",
}

HEAVY_TOPICS = ("sad", "grief", "loss", "lonel", "depress", "hopeless", "cry", "awful", "worse", "hurt", "empty")
PRACTICAL_TOPICS = ("exam", "study", "procrastinat", "sleep", "insomnia", "focus", "concentrat", "time",
                    "motivation", "productiv", "tips", "habit", "breath", "mindful", "ground", "coping",
                    "routine", "burnout", "work")
REFLECTIVE_TOPICS = ("relationship", "breakup", "family", "parent", "esteem", "guilt", "anger", "angry",
                     "jealous", "envy", "overthink", "confiden", "worth", "trust", "friend", "comparison")

OPENERS = {
    "listener": [
        "I'm really glad you shared that with me.",
        "That sounds like a lot to hold right now.",
        "Thank you for telling me — what you're feeling matters.",
    ],
    "coach": [
        "Let's take this one step at a time.",
        "That's a tough spot, and we can work through it together.",
        "Okay — let's make this feel a bit more manageable.",
    ],
    "therapist": [
        "It sounds like this has been weighing on you.",
        "I can hear how much this is affecting you.",
        "It makes sense that you'd feel this way, given what's going on.",
    ],
    "balanced": [
        "I hear you.",
        "That sounds hard, and it's okay to feel this way.",
        "Thanks for sharing that with me.",
    ],
}

CLOSERS = {
    "listener": [
        "Would you like to tell me more about what's been happening?",
        "What part of this feels heaviest right now?",
        "I'm here — take your time.",
    ],
    "coach": [
        "Quick step: pick just one small thing from this you could try in the next 10 minutes.",
        "Quick step: write down the single most urgent thing, then we can break it into smaller pieces.",
        "Which of these feels easiest to start with?",
    ],
    "therapist": [
        "When you notice this feeling, what thought usually comes with it?",
        "If a close friend were in your place, what would you gently say to them?",
        "What do you think this feeling might be trying to tell you?",
    ],
    "balanced": [
        "How does that sound to you?",
        "What do you think might help a little today?",
        "Would you like to try that, or talk it through a bit more?",
    ],
}

OPENERS_NE = {
    "listener": ["मसँग भन्नुभएकोमा साँच्चै खुसी लाग्यो।", "अहिले धेरै बोकिरहनुभएको जस्तो छ।",
                 "भन्नुभएकोमा धन्यवाद — तपाईंको भावना महत्त्वपूर्ण छ।"],
    "coach": ["एक-एक कदम गरौँ।", "यो गाह्रो अवस्था हो, सँगै मिलाउँला।", "ठिक छ — यसलाई अलि सजिलो बनाऔँ।"],
    "therapist": ["यो कुराले तपाईंलाई धेरै असर गरिरहेको जस्तो छ।", "यसले तपाईंलाई कति असर गरिरहेको छ, म बुझ्छु।",
                  "जे भइरहेको छ, त्यसमा यस्तो महसुस हुनु स्वाभाविक हो।"],
    "balanced": ["म सुनिरहेको छु।", "यो गाह्रो हो, र यस्तो महसुस हुनु ठिकै हो।", "भन्नुभएकोमा धन्यवाद।"],
}

CLOSERS_NE = {
    "listener": ["के भइरहेको छ, अलि बढी भन्न चाहनुहुन्छ?", "अहिले सबैभन्दा भारी के लागिरहेको छ?",
                 "म यहीँ छु — समय लिनुहोस्।"],
    "coach": ["सानो कदम: अर्को १० मिनेटमा गर्न सकिने एउटा कुरा छान्नुहोस्।",
              "सानो कदम: सबैभन्दा जरुरी एउटा काम लेख्नुहोस्, अनि त्यसलाई साना भागमा बाँडौँला।",
              "यीमध्ये कुन सुरु गर्न सजिलो लाग्छ?"],
    "therapist": ["यो भावना आउँदा सँगै कस्तो विचार आउँछ?",
                  "तपाईंको ठाउँमा नजिकको साथी भए, उहाँलाई के भन्नुहुन्थ्यो?",
                  "यो भावनाले तपाईंलाई के भन्न खोजिरहेको होला?"],
    "balanced": ["यो कस्तो लाग्यो?", "आज अलिकति मद्दत गर्ने के होला जस्तो लाग्छ?",
                 "यो प्रयास गर्न चाहनुहुन्छ, कि अलि बढी कुरा गरौँ?"],
}

FALLBACK_CORE = {
    "listener": "I may not fully understand yet, but I'm listening and I want to.",
    "coach": "I'm not completely sure I understood, so let's narrow it down together.",
    "therapist": "I want to make sure I understand what you're going through.",
    "balanced": "I'm not sure I fully understood, but I'd like to help.",
}
FALLBACK_NE = {
    "listener": ("मैले अझै पूरा बुझेको नहुन सक्छु, तर म सुनिरहेको छु।",
                 "तपाईंलाई कस्तो महसुस भइरहेको छ, अलि बढी भन्न सक्नुहुन्छ?"),
    "coach": ("मैले पूरा बुझेँ कि बुझिनँ, त्यसैले सँगै स्पष्ट पारौँ।",
              "यो धेरैजसो पढाइ, निद्रा, सम्बन्ध, वा अरू केहीबारे हो?"),
    "therapist": ("तपाईं के भोगिरहनुभएको छ, म राम्ररी बुझ्न चाहन्छु।",
                  "पछिल्लो समय तपाईंको मनमा सबैभन्दा बढी के छ?"),
    "balanced": ("मैले पूरा बुझेँ जस्तो लागेन, तर म मद्दत गर्न चाहन्छु।",
                 "के भइरहेको छ, अलि बढी भन्न सक्नुहुन्छ?"),
}

FALLBACK_CLOSER = {
    "listener": "Could you tell me a little more about how you're feeling?",
    "coach": "Is this mostly about studies, sleep, relationships, or something else?",
    "therapist": "What has been on your mind the most lately?",
    "balanced": "Could you share a bit more about what's going on?",
}


def _has(tag, keywords):
    t = (tag or "").lower()
    return any(k in t for k in keywords)


def select_strategy(preferred_mode, compound=0.0, intent=None):
    """Return the concrete strategy (never "auto")."""
    mode = preferred_mode if preferred_mode in MODES else "auto"
    if mode != "auto":
        return mode
    if compound <= -0.6 or _has(intent, HEAVY_TOPICS):
        return "listener"
    if _has(intent, PRACTICAL_TOPICS):
        return "coach"
    if _has(intent, REFLECTIVE_TOPICS):
        return "therapist"
    return "balanced"


def compose(core, strategy, lang="en"):
    """Wrap core content in the strategy's opener and closer (English or Nepali)."""
    opener = random.choice((OPENERS_NE if lang == "ne" else OPENERS)[strategy])
    closer = random.choice((CLOSERS_NE if lang == "ne" else CLOSERS)[strategy])
    if strategy == "listener":
        core = _first_sentences(core, 2)  # listener keeps advice light
    return f"{opener} {core}\n\n{closer}"


def fallback(strategy, lang="en"):
    """Supportive reply when there is no confident intent and no LLM."""
    if lang == "ne":
        core, closer = FALLBACK_NE[strategy]
        return f"{core}\n\n{closer}"
    return f"{FALLBACK_CORE[strategy]}\n\n{FALLBACK_CLOSER[strategy]}"


def _first_sentences(text, n):
    import re

    parts = re.split(r"(?<=[.!?।])\s+", text.strip())
    return " ".join(parts[:n])
