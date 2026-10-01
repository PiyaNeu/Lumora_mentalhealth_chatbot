| Method | Dataset | Observations (train / val) | Learning rate | Iterations | Accuracy, grouped split | Accuracy, random split |
|---|---|---|---|---|---|---|
| Naive Bayes (TF-IDF) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | -- | -- | 31.84% | 88.88% |
| TF-IDF + Linear SVM | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | -- | 29 (liblinear) | 40.94% | 91.19% |
| Feed-Forward NN (Keras, TF-IDF + history) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | 8e-04 → 4e-04 → 2e-04 | 25 epochs | 43.10% | 96.04% |
| LSTM (Tokenizer + Embedding) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | 1e-03 → 5e-04 | 9 epochs | 31.62% | 90.00% |
