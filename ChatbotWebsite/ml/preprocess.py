"""Text preprocessing shared by training and the running app (report §3.9):
lowercase → punctuation removal → tokenization → WordNet lemmatization.
"""
import re

import nltk
from nltk.stem import WordNetLemmatizer

_PUNCT = re.compile(r"[^\w\sऀ-ॿ]|[_।॥]")
_lemmatizer = WordNetLemmatizer()
_nltk_ready = None


def _ensure_nltk():
    """Download tokenizer/lemmatizer data once; fall back to whitespace split if offline."""
    global _nltk_ready
    if _nltk_ready is None:
        try:
            for pkg, path in (("punkt", "tokenizers/punkt"), ("wordnet", "corpora/wordnet"),
                              ("omw-1.4", "corpora/omw-1.4")):
                try:
                    nltk.data.find(path)
                except LookupError:
                    nltk.download(pkg, quiet=True)
            nltk.word_tokenize("test")
            _lemmatizer.lemmatize("tests")
            _nltk_ready = True
        except Exception:
            _nltk_ready = False
    return _nltk_ready


def clean_text(text):
    """Lowercase and strip punctuation (apostrophes too: "can't" → "cant")."""
    text = (text or "").lower().replace("’", "").replace("'", "")
    return re.sub(r"\s+", " ", _PUNCT.sub(" ", text)).strip()


def tokenize(text):
    cleaned = clean_text(text)
    if not cleaned:
        return []
    if _ensure_nltk():
        tokens = nltk.word_tokenize(cleaned)
        return [_lemmatizer.lemmatize(t) for t in tokens]
    return cleaned.split()


def preprocess(text):
    """Full pipeline → a normalized string used by the TF-IDF vectorizers."""
    return " ".join(tokenize(text))
