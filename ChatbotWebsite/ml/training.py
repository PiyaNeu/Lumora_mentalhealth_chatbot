"""Dataset loading, grouped 80/20 split and the Keras FFNN used by train.py / compare_models.py."""
import json
import os
import random

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_PATH = os.path.join(ROOT, "ChatbotWebsite", "data", "intents_augmented.json")
RANDOM_SEED = 42
HISTORY_NOISE = 0.1  # share of training samples given an unrelated previous message


def set_seeds(seed=RANDOM_SEED):
    import keras

    random.seed(seed)
    np.random.seed(seed)
    keras.utils.set_random_seed(seed)


def load_samples(path=DATASET_PATH):
    """Return (samples, labels). Each sample: dict(text, prev, label, group)."""
    with open(path, encoding="utf-8") as f:
        intents = json.load(f)["intents"]
    labels = [i["tag"] for i in intents]
    samples = []
    for i in intents:
        for text, group in zip(i["patterns"], i["groups"]):
            samples.append({"text": text, "prev": "", "label": i["tag"], "group": group})
        for h in i["history"]:
            samples.append({"text": h["text"], "prev": h["prev"], "label": i["tag"], "group": h["group"]})
    return samples, labels


def grouped_split(samples, val_fraction=0.2, seed=RANDOM_SEED):
    """Stratified 80/20 split where all variants of one base sentence stay on one side."""
    from sklearn.model_selection import StratifiedGroupKFold

    n_splits = round(1 / val_fraction)
    y = [s["label"] for s in samples]
    groups = [s["group"] for s in samples]
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    train_idx, val_idx = next(splitter.split(np.zeros(len(y)), y, groups))
    return [samples[i] for i in train_idx], [samples[i] for i in val_idx]


def add_history_noise(train, seed=RANDOM_SEED):
    """Give some ordinary training samples an unrelated previous message, so the model
    learns that the current message outweighs the history block."""
    rng = random.Random(seed)
    pool = [s["text"] for s in train]
    noisy = []
    for s in train:
        if not s["prev"] and rng.random() < HISTORY_NOISE:
            noisy.append({**s, "prev": rng.choice(pool)})
        else:
            noisy.append(s)
    return noisy


def build_ffnn(input_dim, n_classes, learning_rate=8e-4):
    """Feed-forward network: Dense+ReLU hidden layers, Softmax output (report §3.9)."""
    import keras
    from keras import layers, regularizers

    # Settings chosen in a small search on the grouped validation split (see README)
    l2 = regularizers.l2(1e-5)
    model = keras.Sequential([
        keras.Input(shape=(input_dim,)),
        layers.Dense(128, activation="relu", kernel_regularizer=l2),
        layers.Dropout(0.5),
        layers.Dense(64, activation="relu", kernel_regularizer=l2),
        layers.Dropout(0.5),
        layers.Dense(n_classes, activation="softmax"),
    ])
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
                  loss=keras.losses.CategoricalCrossentropy(label_smoothing=0.1), metrics=["accuracy"])
    return model


def sparse_batches(X, Y, batch_size=32, shuffle=True):
    """keras PyDataset that densifies one sparse batch at a time (keeps memory low)."""
    import keras

    class _Batches(keras.utils.PyDataset):
        def __init__(self):
            super().__init__()
            self.order = np.arange(X.shape[0])
            self.on_epoch_end()

        def __len__(self):
            return int(np.ceil(X.shape[0] / batch_size))

        def __getitem__(self, idx):
            ids = self.order[idx * batch_size:(idx + 1) * batch_size]
            return X[ids].toarray(), Y[ids]

        def on_epoch_end(self):
            if shuffle:
                np.random.shuffle(self.order)

    return _Batches()


def training_callbacks():
    import keras

    return [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=6, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5),
    ]


def train_ffnn(featurizer, train, val, labels, epochs=60, batch_size=32, verbose=2):
    """Fit the FFNN. Returns (model, history_dict, X_val, y_val_idx)."""
    import keras

    label_index = {l: i for i, l in enumerate(labels)}
    X_train = featurizer.transform([s["text"] for s in train], [s["prev"] for s in train])
    X_val = featurizer.transform([s["text"] for s in val], [s["prev"] for s in val])
    y_train = np.array([label_index[s["label"]] for s in train])
    y_val = np.array([label_index[s["label"]] for s in val])
    Y_train = keras.utils.to_categorical(y_train, len(labels))
    Y_val = keras.utils.to_categorical(y_val, len(labels))

    model = build_ffnn(X_train.shape[1], len(labels))
    hist = model.fit(sparse_batches(X_train, Y_train, batch_size),
                     validation_data=sparse_batches(X_val, Y_val, batch_size, shuffle=False),
                     epochs=epochs, callbacks=training_callbacks(), verbose=verbose)
    history = {k: [float(v) for v in vals] for k, vals in hist.history.items()}
    return model, history, X_val, y_val


def predict_sparse(model, X, batch_size=256):
    out = [model.predict(X[i:i + batch_size].toarray(), verbose=0) for i in range(0, X.shape[0], batch_size)]
    return np.vstack(out)
