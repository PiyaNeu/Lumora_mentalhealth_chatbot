"""Intent classification (report §3.7.7b): returns (tag, confidence) plus the response bank.

The classifier is loaded once per app and cached in app.extensions. Tests can
inject a fake by setting app.extensions["lumora_intent"].
"""
import random
import threading

from flask import current_app

EXTENSION_KEY = "lumora_intent"
_load_lock = threading.Lock()


class LegacyIntentClassifier:
    """Mid-term bag-of-words Keras model (chat/chatbot.py). Interim backend until the
    TF-IDF model from train.py is available."""

    name = "legacy-bow"

    def __init__(self):
        from ChatbotWebsite.chat import chatbot as legacy  # loads TensorFlow

        self._legacy = legacy
        self._responses = {i["tag"]: i["responses"] for i in legacy.intents["intents"]}

    def predict(self, text, prev_text=None):
        import numpy as np

        bow = self._legacy.bag_of_words(text, self._legacy.words)
        probs = self._legacy.model.predict(np.array([bow]), verbose=0)[0]
        idx = int(probs.argmax())
        return self._legacy.classes[idx], float(probs[idx])

    def responses(self, tag):
        return self._responses.get(tag, [])


def _load_classifier():
    if not current_app.config.get("LOAD_INTENT_MODEL", True):
        return None
    try:
        return LegacyIntentClassifier()
    except Exception:  # missing model files, TF import failure, etc.
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

    threading.Thread(target=_run, name="intent-preload", daemon=True).start()


def pick_response(classifier, tag, avoid=None):
    options = classifier.responses(tag)
    choices = [r for r in options if r != avoid] or options
    return random.choice(choices) if choices else None
