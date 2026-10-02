"""Intent classification (report §3.7.7b): returns (tag, confidence) plus the response bank.

The classifier is loaded once per app and cached in app.extensions. Tests can
inject a fake by setting app.extensions["lumora_intent"].
"""
import json
import os
import random
import threading

from flask import current_app

from ChatbotWebsite.ml.keras_lock import KERAS_LOCK

EXTENSION_KEY = "lumora_intent"
_load_lock = threading.Lock()


_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATASET_PATH = os.path.join(_DATA_DIR, "intents_augmented.json")
NEPALI_RESPONSES_PATH = os.path.join(_DATA_DIR, "responses_ne.json")

# Intents treated as a crisis even if the keyword safety screen missed the message
CRISIS_INTENTS = {"crisis_suicidal", "self_harm"}

# Closely related intents. When the model splits its probability between members of one
# family ("exam stress" 0.41 vs "stress" 0.28), the family total is used as the confidence
# and the most likely member answers — the model is sure of the topic, just not the sub-topic.
INTENT_FAMILIES = [
    {"stress_general", "exam_stress", "academic_pressure_parents", "burnout", "overwhelm", "time_management",
     "exam_failure_results", "study_focus", "procrastination"},
    {"anxiety_general", "panic_attack", "fear_worry_future", "overthinking", "social_anxiety_shyness",
     "career_uncertainty"},
    {"sadness_low_mood", "crying_emotional", "loneliness", "grief_loss", "low_self_esteem", "homesickness",
     "boredom_lack_interest"},
    {"relationship_problems", "breakup_heartbreak", "family_conflict", "friendship_issues", "bullying_harassment"},
    {"sleep_issues", "nightmares", "tiredness_fatigue"},
    {"breathing_exercise", "mindfulness_grounding", "coping_skills", "self_care", "journaling_prompt"},
    {"crisis_suicidal", "self_harm"},
]
_FAMILY_OF = {tag: i for i, fam in enumerate(INTENT_FAMILIES) for tag in fam}


def family_confidence(labels, probs):
    """(best tag, confidence) where confidence includes same-family probability mass."""
    idx = int(probs.argmax())
    tag = labels[idx]
    fam = _FAMILY_OF.get(tag)
    if fam is None:
        return tag, float(probs[idx])
    total = sum(float(p) for label, p in zip(labels, probs) if _FAMILY_OF.get(label) == fam)
    return tag, min(total, 1.0)


class TfidfIntentClassifier:
    """Keras FFNN over word + char TF-IDF + history features (trained by train.py)."""

    name = "tfidf-ffnn"

    def __init__(self, model_dir):
        import pickle

        import keras

        with open(os.path.join(model_dir, "intent_featurizer.pkl"), "rb") as fh:
            bundle = pickle.load(fh)  # our own artifact written by train.py
        self.featurizer, self.labels = bundle["featurizer"], bundle["labels"]
        with KERAS_LOCK:
            self.model = keras.models.load_model(os.path.join(model_dir, "intent_ffnn.keras"))
        with open(DATASET_PATH, encoding="utf-8") as fh:
            intents = json.load(fh)["intents"]
        self._responses = {i["tag"]: i["responses"] for i in intents}
        with open(NEPALI_RESPONSES_PATH, encoding="utf-8") as fh:
            self._responses_ne = json.load(fh)["responses"]
        self._wrap = {i["tag"]: i.get("wrap", True) for i in intents}

    def predict(self, text, prev_text=None):
        X = self.featurizer.transform([text], [prev_text or ""])
        with KERAS_LOCK:
            probs = self.model.predict(X.toarray(), verbose=0)[0]
        return family_confidence(self.labels, probs)

    def responses(self, tag, lang="en"):
        if lang == "ne" and self._responses_ne.get(tag):
            return self._responses_ne[tag]
        return self._responses.get(tag, [])

    def wraps(self, tag):
        """False for conversational/safety intents whose reply should not get a brain opener."""
        return self._wrap.get(tag, True)


def _load_classifier():
    if not current_app.config.get("LOAD_INTENT_MODEL", True):
        return None
    model_dir = current_app.config["MODEL_DIR"]
    if not os.path.exists(os.path.join(model_dir, "intent_ffnn.keras")):
        current_app.logger.warning("No trained intent model in %s (run train.py); using fallback replies",
                                   model_dir)
        return None
    try:
        return TfidfIntentClassifier(model_dir)
    except Exception:  # corrupt files, TF import failure, etc.
        current_app.logger.exception("Intent model could not be loaded; continuing without it")
        return None


def get_classifier():
    ext = current_app.extensions
    if EXTENSION_KEY not in ext:
        with _load_lock:  # the startup preload thread and a request may race
            if EXTENSION_KEY not in ext:
                ext[EXTENSION_KEY] = _load_classifier()
    return ext[EXTENSION_KEY]


def preload_in_background(app):
    """Load the model at startup so the first chat message isn't slow (TensorFlow takes seconds)."""
    def _run():
        with app.app_context():
            get_classifier()
        from ChatbotWebsite.sentiment import ml_probabilities

        try:
            ml_probabilities(["warm up"])  # loads the sentiment model too
        except Exception:
            app.logger.exception("Sentiment model could not be loaded; hybrid uses VADER + rules only")

    threading.Thread(target=_run, name="intent-preload", daemon=True).start()


def pick_response(classifier, tag, avoid=None, lang="en"):
    """Random response for `tag` in `lang` ("en" or "ne"). Returns (text, lang) — lang is "en" if no
    Nepali response exists for this intent (or the classifier doesn't provide them)."""
    options = []
    if lang == "ne":
        try:
            options = classifier.responses(tag, "ne")
        except TypeError:  # classifiers without language support (e.g. test fakes)
            options = []
        english = classifier.responses(tag)
        if options == english:
            options = []
    if options:
        choices = [r for r in options if r != avoid] or options
        return random.choice(choices), "ne"
    options = classifier.responses(tag)
    choices = [r for r in options if r != avoid] or options
    return (random.choice(choices), "en") if choices else (None, "en")
