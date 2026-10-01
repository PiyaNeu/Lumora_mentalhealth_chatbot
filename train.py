"""Train LUMORA's intent classifier (report §3.9, §5.2).

  word TF-IDF (1–2) + char TF-IDF (3–5) + history features → Keras FFNN
  (Dense+ReLU, Softmax), categorical cross-entropy, Adam, EarlyStopping,
  ReduceLROnPlateau, stratified 80/20 split grouped by base sentence.

Outputs
  model/intent_ffnn.keras         trained model (final model is refit on 100% of the data)
  model/intent_featurizer.pkl     fitted vectorizers + label order
  reports/metrics.json            real validation metrics
  reports/classification_report.txt
  reports/accuracy_curve.png, loss_curve.png, per_intent_prf.png, per_intent_prf_top.png

Usage:  python train.py            (python build_dataset.py first if the dataset changed)
        python train.py --no-refit (keep the 80% model instead of refitting on all data)
"""
import argparse
import json
import os
import pickle
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_recall_fscore_support

from ChatbotWebsite.ml.features import IntentFeaturizer
from ChatbotWebsite.ml.training import (DATASET_PATH, ROOT, add_history_noise, build_ffnn, grouped_split,
                                        load_samples, predict_sparse, set_seeds, sparse_batches, train_ffnn)

MODEL_DIR = os.path.join(ROOT, "model")
REPORT_DIR = os.path.join(ROOT, "reports")


def plot_curves(history, out_dir):
    epochs = range(1, len(history["loss"]) + 1)
    for metric, title, fname in (("accuracy", "Training and Validation Accuracy", "accuracy_curve.png"),
                                 ("loss", "Training and Validation Loss", "loss_curve.png")):
        plt.figure(figsize=(8, 5))
        plt.plot(epochs, history[metric], marker="o", ms=3, label=f"Training {metric}")
        plt.plot(epochs, history[f"val_{metric}"], marker="o", ms=3, label=f"Validation {metric}")
        plt.title(f"LUMORA intent model — {title}")
        plt.xlabel("Epoch")
        plt.ylabel(metric.capitalize())
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, fname), dpi=150)
        plt.close()


def plot_prf(labels, precision, recall, f1, support, out_path, title):
    y = np.arange(len(labels))
    h = 0.27
    plt.figure(figsize=(10, max(4, 0.32 * len(labels))))
    plt.barh(y - h, precision, h, label="Precision")
    plt.barh(y, recall, h, label="Recall")
    plt.barh(y + h, f1, h, label="F1")
    plt.yticks(y, [f"{l} (n={s})" for l, s in zip(labels, support)], fontsize=8)
    plt.xlim(0, 1.05)
    plt.gca().invert_yaxis()
    plt.xlabel("Score")
    plt.title(title)
    plt.legend(loc="lower right")
    plt.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--no-refit", action="store_true")
    args = parser.parse_args()

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    set_seeds()

    samples, labels = load_samples()
    train, val = grouped_split(samples)
    print(f"Dataset: {len(samples)} samples, {len(labels)} intents "
          f"(train {len(train)} / validation {len(val)}, grouped by base sentence)")

    featurizer = IntentFeaturizer().fit([s["text"] for s in train])
    train_noisy = add_history_noise(train)
    model, history, X_val, y_val = train_ffnn(featurizer, train_noisy, val, labels, epochs=args.epochs)

    probs = predict_sparse(model, X_val)
    y_pred = probs.argmax(axis=1)
    acc = accuracy_score(y_val, y_pred)
    macro_f1 = f1_score(y_val, y_pred, average="macro")
    p, r, f, s = precision_recall_fscore_support(y_val, y_pred, labels=range(len(labels)), zero_division=0)

    # Accuracy on the history (follow-up) samples alone, and the same texts without history
    hist_idx = [i for i, smp in enumerate(val) if smp["prev"]]
    hist_acc = float((y_pred[hist_idx] == y_val[hist_idx]).mean()) if hist_idx else None
    if hist_idx:
        X_nohist = featurizer.transform([val[i]["text"] for i in hist_idx])
        nohist_acc = float((predict_sparse(model, X_nohist).argmax(1) == y_val[hist_idx]).mean())
    else:
        nohist_acc = None

    # Confidence behaviour: how many messages pass each threshold, and how accurate those are
    conf = probs.max(axis=1)
    threshold_table = []
    for t in (0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8):
        mask = conf >= t
        threshold_table.append({
            "threshold": t,
            "coverage": round(float(mask.mean()), 4),
            "accuracy_when_confident": round(float((y_pred[mask] == y_val[mask]).mean()), 4) if mask.any() else None,
        })

    best_epoch = int(np.argmin(history["val_loss"])) + 1
    metrics = {
        "model": "Keras FFNN on word TF-IDF (1-2) + char TF-IDF (3-5) + history features",
        "dataset": os.path.relpath(DATASET_PATH, ROOT),
        "samples": len(samples), "intents": len(labels),
        "train_samples": len(train), "validation_samples": len(val),
        "split": "StratifiedGroupKFold 80/20 (variants of one base sentence never span both sides)",
        "feature_dim": featurizer.dim,
        "epochs_run": len(history["loss"]), "best_epoch": best_epoch,
        "learning_rates": sorted(set(round(x, 6) for x in history.get("learning_rate", [])), reverse=True),
        "validation_accuracy": round(float(acc), 4),
        "validation_macro_f1": round(float(macro_f1), 4),
        "final_train_accuracy": round(history["accuracy"][best_epoch - 1], 4),
        "history_followups_accuracy": hist_acc,
        "history_followups_accuracy_without_history": nohist_acc,
        "confidence_thresholds": threshold_table,
        "per_intent": {labels[i]: {"precision": round(float(p[i]), 3), "recall": round(float(r[i]), 3),
                                   "f1": round(float(f[i]), 3), "support": int(s[i])}
                       for i in range(len(labels))},
        "history": history,
    }
    with open(os.path.join(REPORT_DIR, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    with open(os.path.join(REPORT_DIR, "classification_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(classification_report(y_val, y_pred, labels=range(len(labels)),
                                       target_names=labels, zero_division=0, digits=3))

    plot_curves(history, REPORT_DIR)
    plot_prf(labels, p, r, f, s, os.path.join(REPORT_DIR, "per_intent_prf.png"),
             "Per-intent Precision / Recall / F1 (validation)")
    top = np.argsort(-s)[:12]
    plot_prf([labels[i] for i in top], p[top], r[top], f[top], s[top],
             os.path.join(REPORT_DIR, "per_intent_prf_top.png"),
             "Per-intent Precision / Recall / F1 — top intents by support (validation)")

    print(f"\nValidation accuracy: {acc:.4f}   macro-F1: {macro_f1:.4f}   "
          f"(best epoch {best_epoch} of {len(history['loss'])})")
    if hist_idx:
        print(f"Follow-up messages: {hist_acc:.3f} with history vs {nohist_acc:.3f} without")
    for row in threshold_table:
        print(f"  confidence >= {row['threshold']:.2f}: coverage {row['coverage']:.1%}, "
              f"accuracy {row['accuracy_when_confident']}")

    # Final model: refit on all data for the same number of epochs as the best validation epoch
    if not args.no_refit:
        print(f"\nRefitting on all {len(samples)} samples for {best_epoch} epochs...")
        set_seeds()
        featurizer = IntentFeaturizer().fit([s["text"] for s in samples])
        import keras

        label_index = {l: i for i, l in enumerate(labels)}
        all_noisy = add_history_noise(samples)
        X = featurizer.transform([x["text"] for x in all_noisy], [x["prev"] for x in all_noisy])
        Y = keras.utils.to_categorical([label_index[x["label"]] for x in all_noisy], len(labels))
        model = build_ffnn(X.shape[1], len(labels))
        lrs = history.get("learning_rate") or [8e-4] * best_epoch
        schedule = keras.callbacks.LearningRateScheduler(lambda epoch, lr: float(lrs[min(epoch, len(lrs) - 1)]))
        model.fit(sparse_batches(X, Y), epochs=best_epoch, callbacks=[schedule], verbose=2)

    # Save an uncompiled copy: same architecture and weights, without the optimizer state (~3x smaller)
    import keras

    export = keras.Sequential.from_config(model.get_config())  # uncompiled → no optimizer slots
    export.set_weights(model.get_weights())
    export.save(os.path.join(MODEL_DIR, "intent_ffnn.keras"))
    with open(os.path.join(MODEL_DIR, "intent_featurizer.pkl"), "wb") as fh:
        pickle.dump({"featurizer": featurizer, "labels": labels}, fh)
    print(f"Saved model to {MODEL_DIR} and reports to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
