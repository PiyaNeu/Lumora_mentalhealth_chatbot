"""Sentiment analysis (report §3.8.4, §5.3.3 J1).

Three methods, all returning negative / neutral / positive:
  analyze(text)     – VADER (lexicon + rules). Compound score in [-1, 1].
  ml_predict(text)  – small Keras classifier trained by train_sentiment.py
  hybrid(text)      – VADER + ML combined, then mental-health rules:
                        • risk screening hit → negative
                        • mixed feelings ("sad but hopeful") → damped towards neutral
                        • domain words VADER under-scores (overwhelmed, can't sleep…)
The hybrid label is what gets stored for chat messages and journals.
"""
import os
import re
import threading
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ChatbotWebsite.ml.keras_lock import KERAS_LOCK

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05
HYBRID_THRESHOLD = 0.1
LABELS = ("negative", "neutral", "positive")

_analyzer = SentimentIntensityAnalyzer()


@dataclass
class Sentiment:
    compound: float
    label: str  # negative | neutral | positive
    pos: float = 0.0
    neu: float = 0.0
    neg: float = 0.0


def label_for(compound, threshold=POSITIVE_THRESHOLD):
    if compound >= threshold:
        return "positive"
    if compound <= -threshold:
        return "negative"
    return "neutral"


def analyze(text):
    """Score text with VADER. Empty or missing text is neutral (never raises)."""
    if not text or not text.strip():
        return Sentiment(0.0, "neutral", 0.0, 1.0, 0.0)
    s = _analyzer.polarity_scores(text)
    return Sentiment(s["compound"], label_for(s["compound"]), s["pos"], s["neu"], s["neg"])


# ---------------------------------------------------------------- ML classifier
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_DIR = os.path.join(_ROOT, "model")
_ml = {}
_ml_lock = threading.Lock()


def _load_ml(model_dir):
    import pickle

    import keras

    with open(os.path.join(model_dir, "sentiment_featurizer.pkl"), "rb") as fh:
        bundle = pickle.load(fh)  # our own artifact written by train_sentiment.py
    with KERAS_LOCK:
        model = keras.models.load_model(os.path.join(model_dir, "sentiment_ffnn.keras"))
    return bundle["featurizer"], bundle["labels"], model


def ml_available(model_dir=DEFAULT_MODEL_DIR):
    return os.path.exists(os.path.join(model_dir, "sentiment_ffnn.keras"))


def ml_probabilities(texts, model_dir=DEFAULT_MODEL_DIR):
    """Return a list of {label: probability} dicts, or None if the model isn't trained."""
    if not ml_available(model_dir):
        return None
    with _ml_lock:
        if model_dir not in _ml:
            _ml[model_dir] = _load_ml(model_dir)
    featurizer, labels, model = _ml[model_dir]
    X = featurizer.transform(list(texts)).toarray()
    with KERAS_LOCK:
        probs = model.predict(X, verbose=0)
    return [dict(zip(labels, map(float, row))) for row in probs]


def ml_predict(text, model_dir=DEFAULT_MODEL_DIR):
    probs = ml_probabilities([text or ""], model_dir)
    if probs is None:
        return None
    p = probs[0]
    return max(p, key=p.get)


# ---------------------------------------------------------------- Hybrid
NEGATIVE_FEELINGS = re.compile(
    r"\b(sad|down|low|depressed|lonely|alone|anxious|nervous|scared|afraid|worried|stressed|tense|"
    r"tired|exhausted|drained|overwhelmed|hopeless|angry|hurt|cry(ing)?|upset|empty|lost|stuck|"
    r"burn(ed|t)? out|can'?t sleep|insomnia|panic\w*|fail(ed|ing)?|homesick|demotivated|"
    r"guilty|ashamed|worthless|useless|miserable|awful|terrible)\b", re.I)
POSITIVE_FEELINGS = re.compile(
    r"\b(happy|hopeful|better|good|great|calm|relieved|grateful|thankful|proud|excited|okay|fine|"
    r"glad|peaceful|motivated|confident|loved)\b", re.I)
NEGATED_POSITIVE = re.compile(r"\b(not|never|no longer|isn'?t|aren'?t|don'?t feel|can'?t feel)\s+"
                              r"(\w+\s+)?(happy|good|okay|ok|fine|great|better|well)\b", re.I)
DOMAIN_LEXICON = {
    r"\boverwhelm\w*": -0.5, r"\bexhausted\b": -0.4, r"\bburn(ed|t)? ?out\b": -0.5,
    r"\bcan'?t sleep\b": -0.4, r"\binsomnia\b": -0.4, r"\bstressed\b": -0.4, r"\btension\b": -0.3,
    r"\bfail(ed)?\b": -0.4, r"\bhomesick\b": -0.4, r"\bdemotivated\b": -0.4, r"\bdrained\b": -0.4,
    r"\bpanic\w*": -0.5, r"\bno energy\b": -0.4, r"\bcan'?t focus\b": -0.3,
}


@dataclass
class HybridSentiment:
    score: float        # [-1, 1]
    label: str
    vader: float
    ml_label: str = None
    rule: str = ""      # which rule (if any) changed the outcome


def hybrid(text, risk_level=None, model_dir=DEFAULT_MODEL_DIR, ml_probs=None):
    """VADER + ML + rules. `risk_level` comes from the chat safety screen when available."""
    v = analyze(text).compound
    if not text or not text.strip():
        return HybridSentiment(0.0, "neutral", 0.0)

    probs = ml_probs
    if probs is None:
        try:
            probs = (ml_probabilities([text], model_dir) or [None])[0]
        except Exception:  # model files unreadable: fall back to VADER + rules
            probs = None
    ml_label = max(probs, key=probs.get) if probs else None
    # VADER leads; the ML classifier (trained on weak labels) nudges
    score = 0.7 * v + 0.3 * (probs["positive"] - probs["negative"]) if probs else v

    rule = ""
    domain = sum(w for pat, w in DOMAIN_LEXICON.items() if re.search(pat, text, re.I))
    if domain:
        score += domain * 0.5
        rule = "domain_lexicon"
    if NEGATED_POSITIVE.search(text):
        score = min(score, -0.3)
        rule = "negated_positive"
    if NEGATIVE_FEELINGS.search(text) and POSITIVE_FEELINGS.search(text) and not NEGATED_POSITIVE.search(text):
        # Naming a negative and a positive feeling together is never plainly positive
        score = min(score * 0.15, HYBRID_THRESHOLD / 2)
        rule = "mixed_feelings"
    if risk_level in ("medium", "high"):
        score = min(score, -0.6)
        rule = "risk_screen"

    score = max(-1.0, min(1.0, score))
    return HybridSentiment(round(score, 4), label_for(score, HYBRID_THRESHOLD), v, ml_label, rule)
