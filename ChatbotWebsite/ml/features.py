"""Feature extraction for the intent model (report §3.9, §5.3.2):

  word TF-IDF (1–2 grams) of the message
+ character TF-IDF (3–5 grams) of the message  — robust to typos and Roman Nepali spellings
+ "history features": word TF-IDF of the previous user message

The history block lets short follow-ups ("what should I do about it?") inherit the
topic of the previous turn. When there is no previous message it is all zeros.
"""
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

from ChatbotWebsite.ml.preprocess import preprocess

HISTORY_WEIGHT = 1.0


class IntentFeaturizer:
    def __init__(self, word_max_features=5000, char_max_features=8000):
        self.word = TfidfVectorizer(ngram_range=(1, 2), max_features=word_max_features,
                                    sublinear_tf=True, min_df=1)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                    max_features=char_max_features, sublinear_tf=True, min_df=2)

    def fit(self, texts):
        cleaned = [preprocess(t) for t in texts]
        self.word.fit(cleaned)
        self.char.fit(cleaned)
        return self

    @property
    def dim(self):
        return 2 * len(self.word.vocabulary_) + len(self.char.vocabulary_)

    def transform(self, texts, prevs=None):
        cleaned = [preprocess(t) for t in texts]
        prevs = prevs if prevs is not None else [""] * len(texts)
        prev_clean = [preprocess(p) if p else "" for p in prevs]
        word = self.word.transform(cleaned)
        char = self.char.transform(cleaned)
        hist = self.word.transform(prev_clean) * HISTORY_WEIGHT
        return sp.hstack([word, char, hist], format="csr", dtype=np.float32)


class SentimentFeaturizer:
    """word TF-IDF (1–2) + char TF-IDF (3–5) for the ML sentiment classifier."""

    def __init__(self):
        self.word = TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=4000,
                                    sublinear_tf=True, min_df=2)

    def fit(self, texts):
        cleaned = [preprocess(t) for t in texts]
        self.word.fit(cleaned)
        self.char.fit(cleaned)
        return self

    def transform(self, texts):
        cleaned = [preprocess(t) for t in texts]
        return sp.hstack([self.word.transform(cleaned), self.char.transform(cleaned)],
                         format="csr", dtype=np.float32)
