"""Compare intent-classification models (report §5.3, Table 5.3).

  Naive Bayes   – word TF-IDF (1–2 grams)
  Linear SVM    – word TF-IDF (1–2 grams)
  FFNN (Keras)  – word + char TF-IDF + history features (the production model)
  LSTM (Keras)  – tokenizer + embedding

All models use the same dataset and the same 80/20 split. Two splits are reported:
  grouped – variants of one base sentence never appear on both sides (realistic)
  random  – plain stratified random split (variants leak across; optimistic)

Outputs: reports/model_comparison.json, model_comparison.md,
         model_comparison_curve.png (validation accuracy per epoch),
         model_comparison_bar.png
Usage:   python compare_models.py
"""
import json
import os
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC

from ChatbotWebsite.ml.features import IntentFeaturizer
from ChatbotWebsite.ml.preprocess import preprocess
from ChatbotWebsite.ml.training import (ROOT, add_history_noise, grouped_split, load_samples, predict_sparse,
                                        random_split, set_seeds, train_ffnn, training_callbacks)

REPORT_DIR = os.path.join(ROOT, "reports")


def word_tfidf(train, val):
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    Xt = vec.fit_transform([preprocess(s["text"]) for s in train])
    Xv = vec.transform([preprocess(s["text"]) for s in val])
    return Xt, Xv


def run_naive_bayes(train, val):
    Xt, Xv = word_tfidf(train, val)
    model = MultinomialNB(alpha=0.1).fit(Xt, [s["label"] for s in train])
    return {"accuracy": accuracy_score([s["label"] for s in val], model.predict(Xv)),
            "learning_rate": "--", "iterations": "--"}


def run_svm(train, val):
    Xt, Xv = word_tfidf(train, val)
    model = LinearSVC(C=0.5).fit(Xt, [s["label"] for s in train])
    return {"accuracy": accuracy_score([s["label"] for s in val], model.predict(Xv)),
            "learning_rate": "--", "iterations": f"{model.n_iter_} (liblinear)"}


def run_ffnn(train, val, labels):
    set_seeds()
    featurizer = IntentFeaturizer().fit([s["text"] for s in train])
    model, history, X_val, y_val = train_ffnn(featurizer, add_history_noise(train), val, labels, verbose=0)
    acc = float((predict_sparse(model, X_val).argmax(1) == y_val).mean())
    return {"accuracy": acc, "curve": history["val_accuracy"],
            "learning_rate": _lr_text(history), "iterations": f"{len(history['loss'])} epochs"}


def run_lstm(train, val, labels):
    import keras
    from keras import layers

    set_seeds()
    label_index = {l: i for i, l in enumerate(labels)}
    texts_t = np.array([preprocess(s["text"]) for s in train])
    texts_v = np.array([preprocess(s["text"]) for s in val])
    y_t = keras.utils.to_categorical([label_index[s["label"]] for s in train], len(labels))
    y_v = keras.utils.to_categorical([label_index[s["label"]] for s in val], len(labels))

    vectorize = layers.TextVectorization(max_tokens=8000, output_sequence_length=30)
    vectorize.adapt(texts_t)
    Xt, Xv = vectorize(texts_t), vectorize(texts_v)

    model = keras.Sequential([
        keras.Input(shape=(30,), dtype="int64"),
        layers.Embedding(input_dim=8000, output_dim=128, mask_zero=True),
        layers.LSTM(64),
        layers.Dropout(0.4),
        layers.Dense(len(labels), activation="softmax"),
    ])
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="categorical_crossentropy", metrics=["accuracy"])
    hist = model.fit(Xt, y_t, validation_data=(Xv, y_v), epochs=60, batch_size=32,
                     callbacks=training_callbacks(), verbose=0)
    history = {k: [float(x) for x in v] for k, v in hist.history.items()}
    acc = float((model.predict(Xv, verbose=0).argmax(1) == y_v.argmax(1)).mean())
    return {"accuracy": acc, "curve": history["val_accuracy"],
            "learning_rate": _lr_text(history), "iterations": f"{len(history['loss'])} epochs"}


def _lr_text(history):
    lrs = []
    for lr in history.get("learning_rate", []):
        if not lrs or abs(lrs[-1] - lr) > 1e-12:
            lrs.append(lr)
    return " → ".join(f"{lr:.0e}" for lr in lrs) or "--"


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    samples, labels = load_samples()
    results = {}
    for split_name, splitter in (("grouped", grouped_split), ("random", random_split)):
        train, val = splitter(samples)
        print(f"\n== {split_name} split: train {len(train)} / validation {len(val)} ==")
        res = {}
        for name, fn in (("Naive Bayes (TF-IDF)", lambda: run_naive_bayes(train, val)),
                         ("TF-IDF + Linear SVM", lambda: run_svm(train, val)),
                         ("Feed-Forward NN (Keras, TF-IDF + history)", lambda: run_ffnn(train, val, labels)),
                         ("LSTM (Tokenizer + Embedding)", lambda: run_lstm(train, val, labels))):
            r = fn()
            res[name] = r
            print(f"{name:45s} {r['accuracy'] * 100:6.2f}%   lr: {r['learning_rate']}   {r['iterations']}")
        results[split_name] = {"train": len(train), "validation": len(val), "models": res}

    with open(os.path.join(REPORT_DIR, "model_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    lines = ["| Method | Dataset | Observations (train / val) | Learning rate | Iterations | "
             "Accuracy, grouped split | Accuracy, random split |",
             "|---|---|---|---|---|---|---|"]
    g, r = results["grouped"], results["random"]
    for name in g["models"]:
        gm, rm = g["models"][name], r["models"][name]
        lines.append(f"| {name} | Own + mid-term DB, intents_augmented.json | {len(samples)} "
                     f"({g['train']} / {g['validation']}) | {gm['learning_rate']} | {gm['iterations']} | "
                     f"{gm['accuracy'] * 100:.2f}% | {rm['accuracy'] * 100:.2f}% |")
    with open(os.path.join(REPORT_DIR, "model_comparison.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # Validation accuracy per epoch (NB / SVM are single points drawn as flat lines)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, split_name in zip(axes, ("grouped", "random")):
        models = results[split_name]["models"]
        max_ep = max(len(m.get("curve", [])) for m in models.values()) or 1
        for name, m in models.items():
            curve = m.get("curve") or [m["accuracy"]] * max_ep
            ax.plot(range(1, len(curve) + 1), curve, marker="o", ms=3, label=name)
        ax.set_title(f"Validation accuracy — {split_name} split")
        ax.set_xlabel("Epoch")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Validation accuracy")
    axes[1].legend(fontsize=8, loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(REPORT_DIR, "model_comparison_curve.png"), dpi=150)
    plt.close()

    names = list(g["models"])
    x = np.arange(len(names))
    plt.figure(figsize=(10, 5))
    for offset, split_name in ((-0.2, "grouped"), (0.2, "random")):
        vals = [results[split_name]["models"][n]["accuracy"] * 100 for n in names]
        bars = plt.bar(x + offset, vals, 0.4, label=f"{split_name} split")
        for b, v in zip(bars, vals):
            plt.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}", ha="center", fontsize=8)
    plt.xticks(x, [n.split(" (")[0] for n in names])
    plt.ylabel("Validation accuracy (%)")
    plt.ylim(0, 105)
    plt.title("Intent model comparison — validation accuracy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(REPORT_DIR, "model_comparison_bar.png"), dpi=150)
    plt.close()
    print(f"\nSaved comparison to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
