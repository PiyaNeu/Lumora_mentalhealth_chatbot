"""Text preprocessing shared by training and the running app (report §3.9):
lowercase → punctuation removal → tokenization → WordNet lemmatization.
"""
import logging
import re
import threading

import nltk
from nltk.stem import WordNetLemmatizer

_PUNCT = re.compile(r"[^\w\sऀ-ॿ]|[_।॥]")
_lemmatizer = WordNetLemmatizer()
_nltk_ready = False
_download_attempted = False
_init_lock = threading.Lock()
log = logging.getLogger(__name__)

# (package, paths that count as installed — NLTK often keeps corpora zipped)
_NLTK_DATA = (("punkt", ("tokenizers/punkt", "tokenizers/punkt.zip")),
              ("wordnet", ("corpora/wordnet", "corpora/wordnet.zip")))


def _installed(paths):
    for path in paths:
        try:
            nltk.data.find(path)
            return True
        except LookupError:
            continue
    return False


def _ensure_nltk():
    """Make tokenizer + lemmatizer usable, once per process and thread-safely.

    WordNet is loaded lazily by NLTK and its first use is not thread-safe (concurrent
    first calls raise "'WordNetCorpusReader' object has no attribute '_LazyCorpusLoader__args'").
    So it is forced to load inside a lock before any lemmatization. Data is downloaded only
    if it is really missing, and a failure is retried on the next call instead of
    disabling lemmatization for the rest of the process (the model was trained on lemmas).
    """
    global _nltk_ready, _download_attempted
    if _nltk_ready:
        return True
    with _init_lock:
        if _nltk_ready:
            return True
        try:
            missing = [pkg for pkg, paths in _NLTK_DATA if not _installed(paths)]
            if missing and not _download_attempted:
                _download_attempted = True
                for pkg in missing:
                    nltk.download(pkg, quiet=True)
            from nltk.corpus import wordnet

            wordnet.ensure_loaded()
            nltk.word_tokenize("test")
            _lemmatizer.lemmatize("tests")
            _nltk_ready = True
        except Exception:
            log.warning("NLTK not ready; using whitespace tokens without lemmatization for now", exc_info=True)
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
