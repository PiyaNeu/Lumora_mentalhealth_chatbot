"""Intent classification (report §3.7.7b): returns (tag, confidence) plus the response bank.

The classifier is loaded once per app and cached in app.extensions. Tests can
inject a fake by setting app.extensions["lumora_intent"].
"""
import json
import os
import random
import threading

from flask import current_app

EXTENSION_KEY = "lumora_intent"
_load_lock = threading.Lock()


DATASET_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "intents_augmented.json")

# Intents treated as a crisis even if the keyword safety screen missed the message
CRISIS_INTENTS = {"crisis_suicidal", "self_harm"}


class TfidfIntentClassifier:
    """Keras FFNN over word + char TF-IDF + history features (trained by train.py)."""

    name = "tfidf-ffnn"

    def __init__(self, model_dir):
        import pickle

        import keras

        with open(os.path.join(model_dir, "intent_featurizer.pkl"), "rb") as fh:
            bundle = pickle.load(fh)  # our own artifact written by train.py
        self.featurizer, self.labels = bundle["featurizer"], bundle["labels"]
        self.model = keras.models.load_model(os.path.join(model_dir, "intent_ffnn.keras"))
        with open(DATASET_PATH, encoding="utf-8") as fh:
            intents = json.load(fh)["intents"]
        self._responses = {i["tag"]: i["responses"] for i in intents}
        self._wrap = {i["tag"]: i.get("wrap", True) for i in intents}

    def predict(self, text, prev_text=None):
        X = self.featurizer.transform([text], [prev_text or ""])
        probs = self.model.predict(X.toarray(), verbose=0)[0]
        idx = int(probs.argmax())
        return self.labels[idx], float(probs[idx])

    def responses(self, tag):
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


def pick_response(classifier, tag, avoid=None):
    options = classifier.responses(tag)
    choices = [r for r in options if r != avoid] or options
    return random.choice(choices) if choices else None
