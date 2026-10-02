"""Build ChatbotWebsite/data/intents_augmented.json (54 intents).

Sources
  1. ChatbotWebsite/data/intents_seed.json  – hand-written LUMORA patterns + responses
     ChatbotWebsite/data/intents_seed_extra.json – more hand-written everyday phrasings (round 2)
  2. ChatbotWebsite/static/data/intents.json – mid-term dataset; patterns from tags that
     map onto a LUMORA intent are reused (LEGACY_MAP below)

Augmentation (deterministic, seed=42) brings every intent to TARGET_PER_INTENT samples:
  prefixes/suffixes, synonym swaps, a single typo, case/punctuation changes, plus
  "history" samples — generic follow-ups ("what should I do about it?") paired with a
  previous message from the intent, used to train the history features.

Every sample records `group` = the base pattern it came from, so train/validation
splits can keep all variants of one sentence on the same side (no leakage).

Usage:  python build_dataset.py
"""
import json
import os
import random
import re
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
SEED_PATH = os.path.join(ROOT, "ChatbotWebsite", "data", "intents_seed.json")
EXTRA_PATH = os.path.join(ROOT, "ChatbotWebsite", "data", "intents_seed_extra.json")
LEGACY_PATH = os.path.join(ROOT, "ChatbotWebsite", "static", "data", "intents.json")
OUT_PATH = os.path.join(ROOT, "ChatbotWebsite", "data", "intents_augmented.json")

TARGET_PER_INTENT = 124
HISTORY_PER_INTENT = 8
RANDOM_SEED = 42

LEGACY_MAP = {
    "Greeting": "greeting", "Greeting2": "greeting", "Morning": "greeting", "Afternoon": "greeting",
    "Evening": "greeting", "Goodbye": "goodbye", "Thanks": "thanks", "Name": "about_lumora",
    "Creation": "about_lumora", "Purpose": "capabilities_help", "Help": "capabilities_help",
    "Agree": "agreement", "Right": "agreement", "Disagree": "disagreement", "Wrong": "disagreement",
    "Anxiety Feeling": "anxiety_general", "Anxiety Social": "social_anxiety_shyness",
    "Depressed Feeling": "sadness_low_mood", "Sadness Feeling": "sadness_low_mood",
    "Feeling Awful": "sadness_low_mood", "Feeling Worse": "sadness_low_mood",
    "Grief and Loss": "grief_loss", "Loneliness Feeling": "loneliness",
    "Feeling Worthless": "low_self_esteem", "Feeling Insecured": "low_self_esteem",
    "Self Esteem": "low_self_esteem", "Feeling Happy": "positive_mood", "Feeling Better": "positive_mood",
    "Feeling Excited": "positive_mood", "Feeling Hopeful": "positive_mood",
    "Feeling Scared": "fear_worry_future", "Feeling Bored": "boredom_lack_interest",
    "Feeling Tired": "tiredness_fatigue", "Feeling Demotivated": "motivation_goals",
    "Feeling Guilty": "guilt_shame", "Feeling Angry": "anger_frustration",
    "Feeling Jealous": "jealousy_comparison", "Feeling Envious": "jealousy_comparison",
    "Feeling Confused": "overthinking", "Feeling Overwhelmed": "overwhelm",
    "Sleepless Feeling": "sleep_issues", "Sleepless Tips": "sleep_issues",
    "Stressed Feeling": "stress_general", "Stress School": "exam_stress", "Stress Job": "burnout",
    "Stress Family": "family_conflict", "Stress Relationship": "relationship_problems",
    "Stress Tips": "coping_skills", "Suicide Feeling": "crisis_suicidal", "Bully": "bullying_harassment",
    "Breathing Techniques": "breathing_exercise", "Mindfulness Techniques": "mindfulness_grounding",
    "Meditation Techniques": "mindfulness_grounding", "Journal": "journaling_prompt",
    "Self-care Methods": "self_care", "Professional Types": "professional_help",
}

PREFIXES = ["", "", "", "honestly ", "lately ", "i think ", "these days ", "um ", "so ", "right now ",
            "to be honest ", "idk but ", "ugh ", "recently "]
SUFFIXES = ["", "", "", " lately", " these days", " and i don't know what to do", " any advice?",
            " please help", " :(", "...", " right now", " again", " what should i do", " tbh"]
SYNONYMS = {
    "stressed": ["tense", "pressured", "stressed out"], "sad": ["down", "low", "unhappy"],
    "very": ["really", "so", "extremely"], "really": ["very", "so"], "so": ["really", "very"],
    "exam": ["test", "exams", "finals"], "exams": ["tests", "finals", "exam"],
    "can't": ["cannot", "cant", "can not"], "don't": ["do not", "dont"], "i'm": ["i am", "im"],
    "friend": ["bestie", "friends", "mate"], "friends": ["mates", "friend group"],
    "scared": ["afraid", "frightened", "worried"], "anxious": ["nervous", "worried", "uneasy"],
    "tired": ["exhausted", "drained", "worn out"], "angry": ["mad", "annoyed", "furious"],
    "happy": ["glad", "cheerful", "good"], "lonely": ["alone", "isolated"],
    "parents": ["family", "mom and dad"], "study": ["revise", "learn"], "help": ["support", "advice"],
    "always": ["all the time", "constantly"], "feel": ["am feeling", "feel like i'm"],
    "college": ["university", "school", "campus"], "work": ["job", "assignments"],
}
FOLLOW_UPS = [
    "what should i do", "what can i do about it", "it's getting worse", "it happens every day",
    "any tips?", "how do i fix this", "it's been like this for weeks", "why does this keep happening",
    "can you help me with that", "it makes me feel terrible", "i don't know how to handle it",
    "tell me more", "how do i deal with this", "is that normal?",
]
NO_HISTORY_CATEGORIES = {"conversation", "safety"}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def typo(text, rng):
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) > 4 and w.isalpha()]
    if not candidates:
        return text
    i = rng.choice(candidates)
    w = list(words[i])
    j = rng.randrange(1, len(w) - 1)
    if rng.random() < 0.5:
        del w[j]
    else:
        w[j], w[j + 1] = w[j + 1], w[j]
    words[i] = "".join(w)
    return " ".join(words)


def swap_synonym(text, rng):
    words = text.split()
    idx = [i for i, w in enumerate(words) if w.strip("?.!,") in SYNONYMS]
    if not idx:
        return text
    i = rng.choice(idx)
    core = words[i].strip("?.!,")
    words[i] = words[i].replace(core, rng.choice(SYNONYMS[core]))
    return " ".join(words)


def augment(text, rng, short):
    """One random variant of `text`. Short (conversational) and Nepali texts get light changes."""
    out = text
    nepali = bool(DEVANAGARI.search(text))
    if not nepali:
        out = swap_synonym(out, rng) if rng.random() < 0.5 else out
        if not short:
            out = rng.choice(PREFIXES) + out + rng.choice(SUFFIXES)
        if rng.random() < 0.2:
            out = typo(out, rng)
    else:
        out = out + rng.choice(["", "", "।", " ...", " अहिले", " धेरै"])
    r = rng.random()
    if r < 0.15:
        out = out.capitalize()
    elif r < 0.25:
        out = out.rstrip("?.!") + rng.choice(["!", "?", "."])
    return re.sub(r"\s+", " ", out).strip()


def main():
    rng = random.Random(RANDOM_SEED)
    with open(SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)["intents"]
    with open(LEGACY_PATH, encoding="utf-8") as f:
        legacy = json.load(f)["intents"]

    with open(EXTRA_PATH, encoding="utf-8") as f:
        extra = json.load(f)["patterns"]
    by_tag = {i["tag"]: {**i, "patterns": i["patterns"] + extra.get(i["tag"], [])} for i in seed}
    legacy_patterns = {tag: [] for tag in by_tag}
    for item in legacy:
        target = LEGACY_MAP.get(item["tag"])
        if target:
            legacy_patterns[target].extend(p.strip() for p in item["patterns"] if p.strip())

    out_intents, group_id, stats = [], 0, Counter()
    seen_global = set()
    for tag, item in by_tag.items():
        base = []
        for p in item["patterns"] + legacy_patterns[tag]:
            key = p.lower().strip(" .?!")
            if key and key not in seen_global:
                seen_global.add(key)
                base.append(p)
        stats["seed"] += len(item["patterns"])
        stats["legacy_reused"] += len(base) - len(item["patterns"])

        samples, seen = [], set()
        groups = {}
        for p in base:
            groups[p] = group_id
            group_id += 1
            samples.append({"text": p, "group": groups[p], "source": "base"})
            seen.add(p.lower())

        history = []
        if item["category"] not in NO_HISTORY_CATEGORIES:
            for _ in range(HISTORY_PER_INTENT):
                prev = rng.choice(base)
                history.append({"text": rng.choice(FOLLOW_UPS), "prev": prev, "group": groups[prev],
                                "source": "history"})

        short = item["category"] == "conversation"
        target = TARGET_PER_INTENT - len(history)
        attempts = 0
        while len(samples) < target and attempts < target * 50:
            attempts += 1
            p = rng.choice(base)
            variant = augment(p, rng, short)
            if variant.lower() in seen or variant.lower().strip(" .?!") in seen_global:
                continue
            seen.add(variant.lower())
            samples.append({"text": variant, "group": groups[p], "source": "augmented"})

        stats["augmented"] += sum(s["source"] == "augmented" for s in samples)
        stats["history"] += len(history)
        out_intents.append({
            "tag": tag,
            "category": item["category"],
            "wrap": item["wrap"],
            "patterns": [s["text"] for s in samples],
            "groups": [s["group"] for s in samples],
            "history": history,
            "responses": item["responses"],
        })

    total = sum(len(i["patterns"]) + len(i["history"]) for i in out_intents)
    meta = {
        "intents": len(out_intents),
        "samples": total,
        "seed_patterns": stats["seed"],
        "legacy_patterns_reused": stats["legacy_reused"],
        "augmented_patterns": stats["augmented"],
        "history_samples": stats["history"],
        "random_seed": RANDOM_SEED,
        "note": "Generated by build_dataset.py. Patterns in the same group are variants of one base sentence.",
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "intents": out_intents}, f, ensure_ascii=False, indent=1)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
