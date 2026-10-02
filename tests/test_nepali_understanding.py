"""Everyday Nepali (Roman + Devanagari) messages must reach a sensible intent with the real model."""
import os

import pytest

from ChatbotWebsite.chat.intent import TfidfIntentClassifier
from ChatbotWebsite.chat.pipeline import process_message

CASES = [
    ("malai dherai stress bhayo", {"stress_general"}),
    ("padhai ko dherai pressure cha", {"exam_stress", "academic_pressure_parents", "stress_general"}),
    ("bholi exam cha, dar lagiraako cha", {"exam_stress"}),
    ("exam ma fail bhaye", {"exam_failure_results"}),
    ("result ramro aayena", {"exam_failure_results"}),
    ("padhna man lagdaina", {"study_focus", "motivation_goals", "procrastination"}),
    ("kaam pachi sarchu sadhai", {"procrastination"}),
    ("time pugdaina", {"time_management"}),
    ("aama buwa le dherai pressure dinuhuncha", {"academic_pressure_parents"}),
    ("ghar ma sadhai jhagada huncha", {"family_conflict"}),
    ("boyfriend sanga jhagada bhayo", {"relationship_problems"}),
    ("breakup bhayo, dherai dukha lagyo", {"breakup_heartbreak"}),
    ("girlfriend le chhodi", {"breakup_heartbreak"}),
    ("sathiharu le malai bewasta garchan", {"friendship_issues", "loneliness"}),
    ("malai koi sathi chaina", {"loneliness"}),
    ("ma ekdam eklo chu", {"loneliness"}),
    ("raati nindra nai aaudaina", {"sleep_issues"}),
    ("naramro sapana dekhchu", {"nightmares"}),
    ("khana khana man lagdaina", {"appetite_eating_changes"}),
    ("tension le tauko dukhcha", {"physical_symptoms_stress"}),
    ("dherai chinta lagcha", {"anxiety_general"}),
    ("mutu dherai dhadkiyo, saas ferna garo bhayo", {"panic_attack"}),
    ("arulai dekhera ris lagcha", {"jealousy_comparison", "anger_frustration"}),
    ("malai dherai ris uthcha", {"anger_frustration"}),
    ("ma dherai sochchu", {"overthinking"}),
    ("sabai kura ekaichoti aayo", {"overwhelm"}),
    ("bhabishya ko dar lagcha", {"fear_worry_future", "career_uncertainty"}),
    ("k padhne thaha chaina", {"career_uncertainty"}),
    ("dherai thakai lagyo, kehi garna sakdina", {"tiredness_fatigue", "burnout"}),
    ("malai runa man lagyo", {"crying_emotional", "sadness_low_mood"}),
    ("hajurama bitnubhayo", {"grief_loss"}),
    ("ghar ko dherai yaad aayo", {"homesickness"}),
    ("raksi dherai khana thale", {"substance_use"}),
    ("college ma malai hepchan", {"bullying_harassment"}),
    ("saas ferne abhyas sikaunus", {"breathing_exercise"}),
    ("dhyan kasari garne", {"mindfulness_grounding"}),
    ("doctor sanga kura garna man lagyo", {"professional_help"}),
    ("मलाई धेरै चिन्ता लाग्छ", {"anxiety_general"}),
    ("म एक्लो छु", {"loneliness"}),
    ("आज मलाई धेरै रिस उठ्यो", {"anger_frustration"}),
    ("मेरो साथीले धोका दियो", {"friendship_issues"}),
]


@pytest.fixture
def real_model(app):
    model_dir = app.config["MODEL_DIR"]
    if not os.path.exists(os.path.join(model_dir, "intent_ffnn.keras")):
        pytest.skip("run train.py first")
    app.extensions["lumora_intent"] = TfidfIntentClassifier(model_dir)


@pytest.mark.parametrize("text,expected", CASES)
def test_everyday_nepali_understood(real_model, text, expected):
    reply = process_message(text)
    assert reply.route == "intent", (text, reply.route, reply.intent, reply.confidence)
    assert reply.intent in expected, (text, reply.intent)


def test_feeling_useless_gets_cautious_reply(real_model):
    assert process_message("ma aafulai kehi kaam ko chaina jasto lagcha").route == "medium_risk"


# Reported conversation: "i am crying" -> "yes i am having a lot of exam stress" fell back to
# "I'm not sure I understood" because confidence was split between exam_stress and stress_general.
def test_reported_exam_stress_followup_is_understood(real_model):
    reply = process_message("yes i am having a lot of exam stress", prev_user_text="i am crying")
    assert reply.route == "intent" and reply.intent == "exam_stress"


def test_family_confidence_adds_related_intents():
    import numpy as np

    from ChatbotWebsite.chat.intent import family_confidence

    labels = ["exam_stress", "stress_general", "greeting", "sleep_issues"]
    tag, conf = family_confidence(labels, np.array([0.41, 0.28, 0.21, 0.10]))
    assert tag == "exam_stress" and abs(conf - 0.69) < 1e-6
    tag, conf = family_confidence(labels, np.array([0.10, 0.05, 0.45, 0.40]))
    assert tag == "greeting" and abs(conf - 0.45) < 1e-6   # greeting has no family


def test_off_topic_messages_still_fall_back(real_model):
    for text in ("tell me a joke", "what is the capital of france"):
        assert process_message(text).route == "fallback"


def test_predictions_stay_correct_while_another_model_loads(real_model, app):
    """Keras returned wrong probabilities when predicting during another model load."""
    import threading

    from ChatbotWebsite import sentiment
    from ChatbotWebsite.chat.intent import get_classifier

    clf = get_classifier()
    results, stop = [], threading.Event()

    def loop():
        while not stop.is_set():
            results.append(clf.predict("i am crying")[1])

    worker = threading.Thread(target=loop)
    worker.start()
    sentiment._ml.clear()                   # force a fresh load of the sentiment model
    sentiment.ml_probabilities(["warm up"])
    stop.set()
    worker.join()
    assert results and min(results) > 0.9
