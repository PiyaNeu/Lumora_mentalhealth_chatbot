"""Evaluation metrics (report §3.8.5, §5.3.3) computed from the real database.

J1  sentiment: Macro-F1 of VADER, ML and Hybrid against human labels + confusion matrix
J2  feedback:  average rating, helpful rate, rating distribution, per-session summary
J3  outcomes:  sessions used, sentiment trend (recent 7 days − previous 7), assessment change,
               engagement counts and weekly engagement vs sentiment
"""
from collections import Counter, OrderedDict
from datetime import datetime, timedelta
from statistics import mean

from sklearn.metrics import confusion_matrix, f1_score

LABELS = ["negative", "neutral", "positive"]


# ---------------------------------------------------------------- J1
def j1(gold, predictions):
    """gold: [label]; predictions: {method: [label]}. Returns macro-F1 per method + confusion matrices."""
    if not gold:
        return None
    out = {"n": len(gold), "support": dict(Counter(gold)), "macro_f1": {}, "confusion": {}}
    for method, pred in predictions.items():
        out["macro_f1"][method] = round(float(f1_score(gold, pred, labels=LABELS, average="macro",
                                                       zero_division=0)), 3)
        out["confusion"][method] = confusion_matrix(gold, pred, labels=LABELS).tolist()
    return out


# ---------------------------------------------------------------- J2
def j2(feedback):
    """feedback: list of objects with rating, helpful, session_title, created_at."""
    if not feedback:
        return None
    ratings = [f.rating for f in feedback]
    helpful = sum(1 for f in feedback if f.helpful)
    dist = OrderedDict((r, ratings.count(r)) for r in range(1, 6))
    return {
        "total": len(feedback),
        "average": round(mean(ratings), 2),
        "helpful_yes": helpful,
        "helpful_no": len(feedback) - helpful,
        "helpful_rate": round(100 * helpful / len(feedback), 1),
        "distribution": dist,
    }


# ---------------------------------------------------------------- J3
def sentiment_trend(points, now, days=7):
    """Avg(S_recent) − Avg(S_previous) over two consecutive windows of `days` days."""
    recent = [s for t, s in points if now - timedelta(days=days) <= t <= now]
    previous = [s for t, s in points if now - timedelta(days=2 * days) <= t < now - timedelta(days=days)]
    if not recent or not previous:
        return None, (round(mean(recent), 3) if recent else None), (round(mean(previous), 3) if previous else None)
    return round(mean(recent) - mean(previous), 3), round(mean(recent), 3), round(mean(previous), 3)


def assessment_change(results):
    """Latest − earliest score per test. results: objects with test, score, created_at."""
    by_test = {}
    for r in sorted(results, key=lambda r: r.created_at):
        by_test.setdefault(r.test, []).append(r.score)
    return {t: {"first": s[0], "latest": s[-1], "change": s[-1] - s[0], "count": len(s)}
            for t, s in by_test.items()}


def weekly_engagement(session_times, sentiment_points):
    """Sessions per ISO week and average sentiment per week, aligned on the same weeks."""
    def week(t):
        y, w, _ = t.isocalendar()
        return f"{y}-W{w:02d}"

    sessions = Counter(week(t) for t in session_times)
    sent = {}
    for t, s in sentiment_points:
        sent.setdefault(week(t), []).append(s)
    weeks = sorted(set(sessions) | set(sent))
    return {
        "labels": weeks,
        "sessions": [sessions.get(w, 0) for w in weeks],
        "sentiment": [round(mean(sent[w]), 3) if w in sent else None for w in weeks],
    }


def pearson(xs, ys):
    """Correlation for paired values (None pairs dropped). None if fewer than 4 pairs or no variance."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 4:
        return None
    mx, my = mean(p[0] for p in pairs), mean(p[1] for p in pairs)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x, _ in pairs)
    syy = sum((y - my) ** 2 for _, y in pairs)
    if sxx == 0 or syy == 0:
        return None
    return round(sxy / (sxx ** 0.5 * syy ** 0.5), 3)
