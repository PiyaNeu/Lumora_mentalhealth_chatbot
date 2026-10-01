"""Self-assessments (report §2, §3.8.1). Results are indicative only — never a diagnosis.

PHQ-9 and GAD-7 use the standard items and severity bands (Kroenke et al. 2001;
Spitzer et al. 2006); items are reused from the mid-term static/data/tests.json.
The burnout questionnaire is Lumora's own short screen (not a validated instrument).
"""
import json
import os

_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data", "tests.json")
with open(_DATA, encoding="utf-8") as fh:
    _legacy = {t["title"]: t for t in json.load(fh)["tests"]}

FREQUENCY_2W = [("Not at all", 0), ("Several days", 1), ("More than half the days", 2), ("Nearly every day", 3)]
FREQUENCY_5 = [("Never", 0), ("Rarely", 1), ("Sometimes", 2), ("Often", 3), ("Always", 4)]

ASSESSMENTS = {
    "phq9": {
        "title": "PHQ-9 (Mood)",
        "intro": "Over the last 2 weeks, how often have you been bothered by any of the following problems?",
        "questions": [q["question"] for q in _legacy["Depression Test"]["questions"]],
        "options": FREQUENCY_2W,
        # (upper bound inclusive, band, guidance)
        "bands": [
            (4, "Minimal", "Your answers suggest minimal symptoms. Keep up the habits that help you."),
            (9, "Mild", "Your answers suggest mild symptoms. Self-care, routine and talking to someone you trust can help. Check again in two weeks."),
            (14, "Moderate", "Your answers suggest moderate symptoms. Consider talking to a counsellor or doctor."),
            (19, "Moderately severe", "Your answers suggest moderately severe symptoms. Please consider booking a consultation with a professional."),
            (27, "Severe", "Your answers suggest severe symptoms. Please reach out to a mental health professional soon."),
        ],
        "max": 27,
    },
    "gad7": {
        "title": "GAD-7 (Anxiety)",
        "intro": "Over the last 2 weeks, how often have you been bothered by the following problems?",
        "questions": [q["question"] for q in _legacy["Anxiety Test"]["questions"]],
        "options": FREQUENCY_2W,
        "bands": [
            (4, "Minimal", "Your answers suggest minimal anxiety. Keep using what works for you."),
            (9, "Mild", "Your answers suggest mild anxiety. Breathing, grounding and regular routines can help."),
            (14, "Moderate", "Your answers suggest moderate anxiety. Consider talking to a counsellor or doctor."),
            (21, "Severe", "Your answers suggest severe anxiety. Please reach out to a mental health professional soon."),
        ],
        "max": 21,
    },
    "burnout": {
        "title": "Burnout questionnaire",
        "intro": "Thinking about the last month, how often do these apply to you?",
        "questions": [
            "I feel emotionally drained by my studies or work.",
            "I feel exhausted when I wake up and have to face another day.",
            "I feel more detached or cynical about my studies or work than before.",
            "I feel less effective or productive than I used to.",
            "I find it hard to switch off and rest.",
            "I have been neglecting sleep, meals or breaks.",
        ],
        "options": FREQUENCY_5,
        "bands": [
            (7, "Low", "Low burnout signals. Keep protecting your rest and breaks."),
            (15, "Moderate", "Some burnout signals. Try reducing one demand and adding one restoring activity this week."),
            (24, "High", "Strong burnout signals. Rest is a priority — consider talking to someone you trust or a professional."),
        ],
        "max": 24,
    },
}

PHQ9_SELF_HARM_ITEM = 8  # "Thoughts that you would be better off dead, or of hurting yourself"


class IncompleteAnswers(ValueError):
    pass


def score(key, answers):
    """answers: list of option values (ints), one per question.
    Returns dict(score, band, guidance, max, safety_flag). Raises IncompleteAnswers."""
    test = ASSESSMENTS[key]
    allowed = {v for _, v in test["options"]}
    if len(answers) != len(test["questions"]) or any(a not in allowed for a in answers):
        raise IncompleteAnswers("Please answer every question before submitting.")
    total = sum(answers)
    band, guidance = next((b, g) for upper, b, g in test["bands"] if total <= upper)
    safety_flag = key == "phq9" and answers[PHQ9_SELF_HARM_ITEM] > 0
    return {"score": total, "band": band, "guidance": guidance, "max": test["max"], "safety_flag": safety_flag}


def parse_answers(key, form):
    """Read q0..qN from a submitted form. Missing/invalid answers become None."""
    out = []
    for i in range(len(ASSESSMENTS[key]["questions"])):
        raw = form.get(f"q{i}")
        out.append(int(raw) if raw is not None and raw.lstrip("-").isdigit() else None)
    return out
