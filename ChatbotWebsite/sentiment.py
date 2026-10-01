"""VADER sentiment (report §3.8.4): compound score in [-1, 1] → negative / neutral / positive."""
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

_analyzer = SentimentIntensityAnalyzer()


@dataclass
class Sentiment:
    compound: float
    label: str  # negative | neutral | positive
    pos: float = 0.0
    neu: float = 0.0
    neg: float = 0.0


def label_for(compound):
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def analyze(text):
    """Score text with VADER. Empty or missing text is neutral (never raises)."""
    if not text or not text.strip():
        return Sentiment(0.0, "neutral", 0.0, 1.0, 0.0)
    s = _analyzer.polarity_scores(text)
    return Sentiment(s["compound"], label_for(s["compound"]), s["pos"], s["neu"], s["neg"])
