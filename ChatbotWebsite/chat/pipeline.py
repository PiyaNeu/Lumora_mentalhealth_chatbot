"""LUMORA hybrid response pipeline (report §3.7):

  input → language detection → basic translation → RISK-FIRST safety screen
        → rule guards → intent classifier (confidence threshold)
        → Mistral fallback when confidence is low → brain strategy → humanizer

Session handling (guest vs logged-in) is done by the route; this module is pure
message-in / reply-out so it can be unit-tested without a database.
"""
from dataclasses import dataclass, field

from flask import current_app

from ChatbotWebsite.chat import brain, llm
from ChatbotWebsite.chat.guards import check_guards, pick
from ChatbotWebsite.chat.humanizer import humanize
from ChatbotWebsite.chat.intent import CRISIS_INTENTS, get_classifier, pick_response
from ChatbotWebsite.chat.language import detect_language, is_nepali
from ChatbotWebsite.chat.safety import MEDIUM_REPLY, SOS_REPLY, assess_risk
from ChatbotWebsite.chat.translate import to_english
from ChatbotWebsite.sentiment import Sentiment, analyze

MAX_INPUT_CHARS = 2000
# Lower than the normal threshold on purpose: for crisis intents a false alarm is the safer error
CRISIS_MODEL_THRESHOLD = 0.4

NEPALI_UNAVAILABLE_NOTE = "(नेपाली अनुवाद अहिले उपलब्ध छैन, त्यसैले म अंग्रेजीमा जवाफ दिँदैछु।)"


@dataclass
class ChatReply:
    text: str
    route: str              # sos | medium_risk | guard | intent | llm | fallback
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
    tag, confidence = (None, None)
    if classifier is not None:
        prev_en = to_english(prev_user_text, detect_language(prev_user_text)) if prev_user_text else None
        tag, confidence = classifier.predict(text_en, prev_en)
    threshold = current_app.config["INTENT_CONFIDENCE_THRESHOLD"]
    confident = tag is not None and confidence is not None and confidence >= threshold

    # Second safety net: the model recognised a crisis the keyword rules missed
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
            body, route, reply_lang = brain.fallback(strategy, ui_lang), "fallback", ui_lang

    # 7. Humanizer (also enforces non-diagnostic wording)
    body = humanize(body, reply_lang)

    if ui_lang == "ne" and reply_lang == "en":
        translated = llm.translate_to_nepali(body)
        body = humanize(translated, "ne") if translated else f"{NEPALI_UNAVAILABLE_NOTE}\n\n{body}"

    return ChatReply(body, route, lang, "none", "", tag, confidence, strategy, sentiment, text_en)
