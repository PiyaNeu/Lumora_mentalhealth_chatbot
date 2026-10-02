| Method | Dataset | Observations (train / val) | Learning rate | Iterations | Accuracy, grouped split | Accuracy, random split |
|---|---|---|---|---|---|---|
| Naive Bayes (TF-IDF) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | -- | -- | 50.26% | 87.61% |
| TF-IDF + Linear SVM | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | -- | 29 (liblinear) | 56.30% | 90.07% |
| Feed-Forward NN (Keras, TF-IDF + history) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | 8e-04 → 4e-04 | 26 epochs | 61.37% | 94.70% |
| LSTM (Tokenizer + Embedding) | Own + mid-term DB, intents_augmented.json | 6696 (5355 / 1341) | 1e-03 → 5e-04 | 13 epochs | 48.84% | 88.73% |
