"""LUMORA hybrid response pipeline (report §3.7):

  input → language detection → basic translation → RISK-FIRST safety screen
        → rule guards → intent classifier (confidence threshold)
        → Mistral fallback when confidence is low → brain strategy → humanizer

Session handling (guest vs logged-in) is done by the route; this module is pure
message-in / reply-out so it can be unit-tested without a database.
"""
import re
from dataclasses import dataclass, field

from flask import current_app

from ChatbotWebsite.chat import brain, llm
from ChatbotWebsite.chat.guards import check_guards, pick
from ChatbotWebsite.chat.humanizer import humanize
from ChatbotWebsite.chat.intent import CRISIS_INTENTS, get_classifier, pick_response
from ChatbotWebsite.chat.language import detect_language, is_nepali
from ChatbotWebsite.chat.safety import MEDIUM_REPLY, SOS_REPLY, assess_risk
from ChatbotWebsite.chat.topics import check_line, confirm_question
from ChatbotWebsite.chat.translate import to_english
from ChatbotWebsite.sentiment import Sentiment, analyze

MAX_INPUT_CHARS = 2000
# Lower than the normal threshold on purpose: for crisis intents a false alarm is the safer error
CRISIS_MODEL_THRESHOLD = 0.4
# Between this and INTENT_CONFIDENCE_THRESHOLD the model's best guess is offered tentatively
# ("it sounds like this might be about X — is that right?") instead of a generic fallback.
SOFT_GUESS_THRESHOLD = 0.3

NEPALI_UNAVAILABLE_NOTE = "(नेपाली अनुवाद अहिले उपलब्ध छैन, त्यसैले म अंग्रेजीमा जवाफ दिँदैछु।)"


SHORT_LOW_MOOD = re.compile(
    r"^(i'?m |i am |im |feeling |i feel |it'?s |its |honestly |kinda |pretty |very |so |really |a )*"
    r"(not (good|great|okay|ok|fine|well|so good|too good|that good|happy)|"
    r"not feeling (well|good|great|okay|ok|myself)|bad|awful|terrible|horrible|"
    r"sad|down|low|upset|miserable|rough|bad day|rough day|terrible day|awful day|a bad day|not a good day|"
    r"could be better|been better|not my day)( mentally| emotionally)?( today| lately| right now)?[\s.!]*$",
    re.IGNORECASE,
)
SHORT_GOOD_MOOD = re.compile(
    r"^(i'?m |i am |im |feeling |i feel |it'?s |its |pretty |very |so |really |a )*"
    r"(good|great|happy|fine|well|better|awesome|amazing|good day|great day|nice day)( today| now)?[\s.!]*$",
    re.IGNORECASE,
)


# Messages that only make sense as a follow-up to the previous topic
FOLLOW_UP = re.compile(
    r"\b(what (should|can|do) i( do)?|what now|how (do|can|should) i|any (tips|advice|ideas|suggestions)|"
    r"tips|advice|help( me)?|what do you suggest|why does (this|it)|it'?s getting worse|is (that|this|it) normal|"
    r"tell me more|more (tips|ideas)|anything else|what else|i don'?t know how to (handle|deal with) (it|this)|"
    r"k garne|ke garne|k garu|ke garu|ke garum)\b",
    re.IGNORECASE,
)


def mood_shortcut(text_en):
    """Short answers to "how are you / how was your day" that the model rarely saw in training."""
    text = (text_en or "").strip()
    if len(text.split()) > 6:
        return None
    if SHORT_LOW_MOOD.match(text):
        return "sadness_low_mood", 0.9
    if SHORT_GOOD_MOOD.match(text):
        return "positive_mood", 0.9
    return None


def _soft_guess(classifier, tag, confidence, ui_lang):
    """Offer the model's best guess tentatively. Returns (body, route, lang) or (None, None, None)."""
    if classifier is None or tag is None or confidence is None or confidence < SOFT_GUESS_THRESHOLD:
        return None, None, None
    core, lang = pick_response(classifier, tag, lang=ui_lang)
    intro = check_line(tag, lang)  # None for conversational, upbeat and crisis intents
    if not core or intro is None:
        return None, None, None
    first_two = " ".join(re.split(r"(?<=[.!?।])\s+", core.strip())[:2])
    return f"{intro} {first_two}\n\n{confirm_question(lang)}", "soft_guess", lang


@dataclass
class ChatReply:
    text: str
    route: str              # sos | medium_risk | guard | intent | soft_guess | llm | fallback
    language: str = "en"
    risk: str = "none"
    matched: str = ""
    intent: str = None
    confidence: float = None
    strategy: str = None
    sentiment: Sentiment = field(default_factory=lambda: analyze(""))
    text_en: str = ""   # translated text, used for sentiment storage

    @property
    def sos(self):
        return self.route == "sos"


def process_message(text, mode="auto", history=None, prev_user_text=None, last_bot_text=None):
    """Run one user message through the pipeline. Raises ValueError for empty input."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Message is empty")
    raw = raw[:MAX_INPUT_CHARS]

    # 1. Language detection + basic translation
    lang = detect_language(raw)
    text_en = to_english(raw, lang)
    sentiment = analyze(text_en)
    ui_lang = "ne" if is_nepali(lang) else "en"

    # 2. Risk-first safety screening (raw and translated text)
    risk = assess_risk(raw, text_en)
    if risk.is_high:
        return ChatReply(SOS_REPLY[ui_lang], "sos", lang, "high", risk.matched,
                         sentiment=sentiment, text_en=text_en)
    if risk.is_medium:
        return ChatReply(MEDIUM_REPLY[ui_lang], "medium_risk", lang, "medium", risk.matched,
                         sentiment=sentiment, text_en=text_en)

    # 3. Rule-based guards
    guard = check_guards(text_en, raw)
    if guard:
        name, replies = guard
        return ChatReply(pick(replies, lang, avoid=last_bot_text), "guard", lang,
                         intent=name, sentiment=sentiment, text_en=text_en)

    # 4. Intent classifier with confidence threshold
    classifier = get_classifier()
    # Replies come from the classifier's response bank, so the shortcut needs a classifier too
    tag, confidence = (mood_shortcut(text_en) if classifier is not None else None) or (None, None)
    if classifier is not None and tag is None:
        prev_en = to_english(prev_user_text, detect_language(prev_user_text)) if prev_user_text else None
        # Candidate readings: the message with and without conversation history (history helps
        # follow-ups like "what should I do?" but must not drown out a clear message), and for
        # Nepali also the original text (the model learned some Nepali phrasings directly).
        use_history = bool(prev_en) and bool(FOLLOW_UP.search(text_en))
        candidates = [(text_en, None)] + ([(text_en, prev_en)] if use_history else [])
        if text_en != raw:
            candidates += [(raw, None)] + ([(raw, prev_en)] if use_history else [])
        tag, confidence = max((classifier.predict(t, p) for t, p in candidates), key=lambda r: r[1])
        # Short follow-up ("what should I do?", "any tips?"): if the previous message had a clear
        # topic, continue with exactly that topic — more precise than the history-aware reading.
        threshold = current_app.config["INTENT_CONFIDENCE_THRESHOLD"]
        own_tag, own_conf = classifier.predict(text_en)
        if use_history and len(text_en.split()) <= 8 and own_conf < threshold:
            prev_tag, prev_conf = classifier.predict(prev_en)
            if prev_conf >= threshold and prev_tag not in CRISIS_INTENTS and getattr(
                    classifier, "wraps", lambda t: True)(prev_tag):
                tag, confidence = prev_tag, prev_conf
    threshold = current_app.config["INTENT_CONFIDENCE_THRESHOLD"]
    confident = tag is not None and confidence is not None and confidence >= threshold

    # Second safety net: the model recognised a crisis the keyword rules missed
    if tag in CRISIS_INTENTS and confidence is not None and SOFT_GUESS_THRESHOLD <= confidence < CRISIS_MODEL_THRESHOLD:
        # Possibly a crisis, but not clear: never answer casually — use the cautious reply
        return ChatReply(MEDIUM_REPLY[ui_lang], "medium_risk", lang, "medium", f"model:{tag}", tag, confidence,
                         sentiment=sentiment, text_en=text_en)
    if tag in CRISIS_INTENTS and confidence is not None and confidence >= CRISIS_MODEL_THRESHOLD:
        return ChatReply(SOS_REPLY[ui_lang], "sos", lang, "high", f"model:{tag}", tag, confidence,
                         sentiment=sentiment, text_en=text_en)

    # 5. Brain: choose the response style
    strategy = brain.select_strategy(mode, sentiment.compound, tag if confident else None)

    body, route, reply_lang = None, None, "en"
    if confident:
        core, reply_lang = pick_response(classifier, tag, lang=ui_lang)
        if core:
            wraps = getattr(classifier, "wraps", lambda t: True)(tag)
            body = brain.compose(core, strategy, reply_lang) if wraps else core
            route = "intent"

    # 6. Generative fallback (Mistral) for low confidence / open-ended messages
    if body is None:
        generated = llm.generate_reply(raw, strategy, lang, history)
        if generated:
            body, route = generated, "llm"
            reply_lang = ui_lang  # the LLM is asked to answer in the user's language
        else:
            body, route, reply_lang = _soft_guess(classifier, tag, confidence, ui_lang)
            if body is None:
                body, route, reply_lang = brain.fallback(strategy, ui_lang), "fallback", ui_lang

    # 7. Humanizer (also enforces non-diagnostic wording)
    body = humanize(body, reply_lang)

    if ui_lang == "ne" and reply_lang == "en":
        translated = llm.translate_to_nepali(body)
        body = humanize(translated, "ne") if translated else f"{NEPALI_UNAVAILABLE_NOTE}\n\n{body}"

    return ChatReply(body, route, lang, "none", "", tag, confidence, strategy, sentiment, text_en)
