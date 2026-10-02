"""Intent dataset, preprocessing, features and the model-based crisis safety net."""
import json
import os

import pytest

from ChatbotWebsite.chat.pipeline import process_message
from ChatbotWebsite.ml.features import IntentFeaturizer
from ChatbotWebsite.ml.preprocess import clean_text, preprocess
from ChatbotWebsite.ml.training import DATASET_PATH, grouped_split, load_samples

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dataset_has_54_intents_with_responses():
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    intents = data["intents"]
    assert len(intents) == 54
    assert len({i["tag"] for i in intents}) == 54
    for i in intents:
        assert i["responses"], i["tag"]
        assert len(i["patterns"]) == len(i["groups"])


def test_responses_contain_no_phone_numbers_or_diagnoses():
    import re

    with open(DATASET_PATH, encoding="utf-8") as f:
        intents = json.load(f)["intents"]
    for i in intents:
        for r in i["responses"]:
            assert not re.search(r"\d{3,}[-\s]?\d{3,}", r), (i["tag"], r)
            assert not re.search(r"\byou (have|are suffering from) (depression|an? \w* ?disorder)", r, re.I)


def test_grouped_split_keeps_variants_together():
    samples, _ = load_samples()
    train, val = grouped_split(samples)
    assert abs(len(val) / len(samples) - 0.2) < 0.03
    assert not {s["group"] for s in train} & {s["group"] for s in val}


@pytest.mark.parametrize("text,expected", [
    ("I can't SLEEP!!", "i cant sleep"),
    ("मलाई निद्रा लाग्दैन।", "मलाई निद्रा लाग्दैन"),
    ("", ""),
])
def test_clean_text(text, expected):
    assert clean_text(text) == expected


def test_preprocess_lemmatizes():
    assert preprocess("my exams are coming") == "my exam are coming"


def test_featurizer_history_block_changes_vector():
    f = IntentFeaturizer().fit(["i am stressed about exams", "i cannot sleep at night", "what should i do"])
    without = f.transform(["what should i do"])
    with_prev = f.transform(["what should i do"], ["i cannot sleep at night"])
    assert without.shape == with_prev.shape == (1, f.dim)
    assert with_prev.nnz > without.nnz


def test_model_crisis_intent_triggers_sos_even_without_keywords(app):
    class CrisisModel:
        def predict(self, text, prev=None):
            return "crisis_suicidal", 0.8

        def responses(self, tag):
            return ["should not be used"]

    app.extensions["lumora_intent"] = CrisisModel()
    reply = process_message("everything feels pointless and i have a plan")
    assert reply.route == "sos" and reply.risk == "high"


def test_conversational_intent_reply_is_not_wrapped(app):
    class ThanksModel:
        def predict(self, text, prev=None):
            return "thanks", 0.99

        def responses(self, tag):
            return ["You're very welcome."]

        def wraps(self, tag):
            return False

    app.extensions["lumora_intent"] = ThanksModel()
    assert process_message("thank you so much").text == "You're very welcome."


MODEL_FILE = os.path.join(ROOT, "model", "intent_ffnn.keras")


@pytest.mark.skipif(not os.path.exists(MODEL_FILE), reason="run train.py first")
def test_trained_model_loads_and_predicts_known_intents():
    from ChatbotWebsite.chat.intent import TfidfIntentClassifier

    clf = TfidfIntentClassifier(os.path.join(ROOT, "model"))
    assert len(clf.labels) == 54
    tag, conf = clf.predict("i can't sleep at night")
    assert tag == "sleep_issues" and 0 <= conf <= 1


def test_preprocess_stays_lemmatized_under_concurrent_first_use():
    """A transient NLTK error on concurrent first use used to switch lemmatization off for the
    whole process, silently degrading every prediction (the model is trained on lemmas)."""
    import threading

    from ChatbotWebsite.ml import preprocess as pp

    pp._nltk_ready = False  # simulate a fresh process
    out = []
    threads = [threading.Thread(target=lambda: out.append(pp.preprocess("i am crying about my exams")))
               for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert set(out) == {"i am cry about my exam"}
    assert pp._nltk_ready is True
