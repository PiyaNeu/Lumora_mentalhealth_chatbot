"""Train the ML sentiment classifier used by J1 and the hybrid sentiment model.

Training labels are derived from the intent dataset (distant supervision): each
intent is mapped to the sentiment its messages typically carry (intent_sentiment()),
plus the hand-written ChatbotWebsite/data/sentiment_extra.json (neutral everyday
statements and explicit feeling sentences the intent data lacks).
It is a weak signal — real evaluation (J1) happens on human-labelled chat messages
from the Manual Labeling page, which this model never trains on.

Model: word TF-IDF (1–2) + char TF-IDF (3–5) → Keras FFNN (Dense+ReLU, Softmax),
categorical cross-entropy, Adam, EarlyStopping, ReduceLROnPlateau, stratified 80/20.

Outputs: model/sentiment_ffnn.keras, model/sentiment_featurizer.pkl,
         reports/sentiment_metrics.json
Usage:   python train_sentiment.py
"""
import json
import os
import pickle
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score

from ChatbotWebsite.ml.features import SentimentFeaturizer
from ChatbotWebsite.ml.training import ROOT, load_samples, random_split, set_seeds, sparse_batches, training_callbacks

MODEL_DIR = os.path.join(ROOT, "model")
REPORT_DIR = os.path.join(ROOT, "reports")
LABELS = ["negative", "neutral", "positive"]
EXTRA_PATH = os.path.join(ROOT, "ChatbotWebsite", "data", "sentiment_extra.json")

POSITIVE = {"positive_mood", "thanks"}
NEUTRAL = {"greeting", "goodbye", "about_lumora", "capabilities_help", "agreement", "breathing_exercise",
           "mindfulness_grounding", "journaling_prompt", "coping_skills", "professional_help", "self_care",
           "time_management", "study_focus"}


def intent_sentiment(tag):
    if tag in POSITIVE:
        return "positive"
    if tag in NEUTRAL:
        return "neutral"
    return "negative"


def build_model(input_dim):
    import keras
    from keras import layers

    model = keras.Sequential([
        keras.Input(shape=(input_dim,)),
        layers.Dense(64, activation="relu"),
        layers.Dropout(0.5),
        layers.Dense(len(LABELS), activation="softmax"),
    ])
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="categorical_crossentropy", metrics=["accuracy"])
    return model


def main():
    import keras

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    set_seeds()
    samples, _ = load_samples()
    samples = [{**s, "sentiment": intent_sentiment(s["label"])} for s in samples if not s["prev"]]
    with open(EXTRA_PATH, encoding="utf-8") as fh:
        extra = json.load(fh)
    for label in LABELS:
        for text in extra[label]:
            samples.append({"text": text, "prev": "", "sentiment": label, "group": -1})
    for s in samples:
        s["label"] = s["sentiment"]  # random_split stratifies on "label"
    train, val = random_split(samples)

    featurizer = SentimentFeaturizer().fit([s["text"] for s in train])
    idx = {l: i for i, l in enumerate(LABELS)}
    Xt, Xv = featurizer.transform([s["text"] for s in train]), featurizer.transform([s["text"] for s in val])
    yt = np.array([idx[s["sentiment"]] for s in train])
    yv = np.array([idx[s["sentiment"]] for s in val])
    counts = np.bincount(yt, minlength=3)
    class_weight = {i: len(yt) / (3 * c) for i, c in enumerate(counts)}  # positive class is small

    model = build_model(Xt.shape[1])
    hist = model.fit(sparse_batches(Xt, keras.utils.to_categorical(yt, 3)),
                     validation_data=sparse_batches(Xv, keras.utils.to_categorical(yv, 3), shuffle=False),
                     epochs=40, callbacks=training_callbacks(), class_weight=class_weight, verbose=2)
    pred = model.predict(Xv.toarray(), verbose=0).argmax(1)

    # VADER on the same validation texts, for reference
    from ChatbotWebsite.sentiment import analyze

    vader = np.array([idx[analyze(s["text"]).label] for s in val])
    metrics = {
        "labels_source": "intent tags mapped to sentiment (distant supervision) + data/sentiment_extra.json",
        "class_counts_train": dict(zip(LABELS, map(int, counts))),
        "train_samples": len(train), "validation_samples": len(val),
        "epochs_run": len(hist.history["loss"]),
        "ml_accuracy": round(float(accuracy_score(yv, pred)), 4),
        "ml_macro_f1": round(float(f1_score(yv, pred, average="macro")), 4),
        "vader_macro_f1_same_val": round(float(f1_score(yv, vader, average="macro")), 4),
        "ml_report": classification_report(yv, pred, target_names=LABELS, digits=3, output_dict=True),
        "note": "These are agreement with intent-derived labels. J1 (Evaluation page) measures all methods "
                "against human labels.",
    }
    with open(os.path.join(REPORT_DIR, "sentiment_metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    export = keras.Sequential.from_config(model.get_config())  # uncompiled → small file
    export.set_weights(model.get_weights())
    export.save(os.path.join(MODEL_DIR, "sentiment_ffnn.keras"))
    with open(os.path.join(MODEL_DIR, "sentiment_featurizer.pkl"), "wb") as fh:
        pickle.dump({"featurizer": featurizer, "labels": LABELS}, fh)

    print(f"ML sentiment: accuracy {metrics['ml_accuracy']}, macro-F1 {metrics['ml_macro_f1']} "
          f"(VADER on same texts: macro-F1 {metrics['vader_macro_f1_same_val']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
