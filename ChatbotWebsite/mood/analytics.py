"""Mood dashboard analytics (report §3.8.2): aggregation + trend summaries.

Pure functions over (local datetime, value) points so they're easy to test.
Mood values are on the 1–5 scale; chat sentiment scores are in [-1, 1].
"""
from collections import OrderedDict
from datetime import date, timedelta
from statistics import mean

POSITIVE_DAY = 4.0     # a day whose average mood is Good or better
TREND_DELTA = 0.5      # change in 7-day average that counts as a trend


def mood_from_sentiment(score):
    """Map a hybrid sentiment score [-1, 1] onto the 1–5 mood scale."""
    if score is None:
        return None
    if score <= -0.6:
        return 1
    if score <= -0.2:
        return 2
    if score < 0.2:
        return 3
    if score < 0.6:
        return 4
    return 5


def _bucket(d, period):
    if period == "weekly":
        start = d - timedelta(days=d.weekday())  # Monday
        return start, f"Week of {start:%d %b}"
    if period == "monthly":
        return date(d.year, d.month, 1), f"{d:%b %Y}"
    return d, f"{d:%d %b}"


def aggregate(points, period="daily"):
    """[(datetime, value)] → OrderedDict label → average, oldest first."""
    buckets = {}
    for dt, value in points:
        if value is None:
            continue
        key, label = _bucket(dt.date() if hasattr(dt, "date") else dt, period)
        buckets.setdefault(key, [label, []])[1].append(value)
    return OrderedDict((buckets[k][0], round(mean(buckets[k][1]), 2)) for k in sorted(buckets))


def daily_means(points):
    by_day = {}
    for dt, value in points:
        by_day.setdefault(dt.date() if hasattr(dt, "date") else dt, []).append(value)
    return {d: mean(v) for d, v in by_day.items()}


def positive_streak(points, today):
    """Consecutive days, ending today or yesterday, whose average mood is Good or better."""
    days = daily_means(points)
    d = today if today in days else today - timedelta(days=1)
    streak = 0
    while d in days and days[d] >= POSITIVE_DAY:
        streak += 1
        d -= timedelta(days=1)
    return streak


def stats(points, today):
    values = [v for _, v in points]
    if not values:
        return None
    return {
        "average": round(mean(values), 2),
        "min": min(values),
        "max": max(values),
        "count": len(values),
        "streak": positive_streak(points, today),
    }


def trend(points, today):
    """Compare the last 7 days with the 7 before. Returns (direction, delta)."""
    days = daily_means(points)
    recent = [v for d, v in days.items() if today - timedelta(days=6) <= d <= today]
    previous = [v for d, v in days.items() if today - timedelta(days=13) <= d <= today - timedelta(days=7)]
    if not recent or not previous:
        return "not_enough_data", None
    delta = round(mean(recent) - mean(previous), 2)
    if delta <= -TREND_DELTA:
        return "down", delta
    if delta >= TREND_DELTA:
        return "up", delta
    return "stable", delta


def recent_low_run(points, today, days=3):
    """True if each of the last `days` days with data averaged Low or worse."""
    by_day = daily_means(points)
    recent = [by_day[d] for d in sorted(by_day) if d <= today][-days:]
    return len(recent) == days and all(v <= 2 for v in recent)


def insight(points, today):
    """Plain-language insight + suggestion. Indicative only, never diagnostic."""
    direction, delta = trend(points, today)
    low_run = recent_low_run(points, today)
    if low_run:
        return {
            "level": "warning",
            "insight": "Your last few check-ins have been low.",
            "suggestion": "Be gentle with yourself. Try a breathing exercise, reach out to someone you trust, "
                          "and consider talking to a professional. If you feel unsafe, use the SOS page.",
        }
    if direction == "down":
        return {
            "level": "warning",
            "insight": f"Downward trend detected (7-day average {delta:+.2f}).",
            "suggestion": "Consider journaling and reflecting on what influenced your days, and keep up sleep, "
                          "meals and small breaks.",
        }
    if direction == "up":
        return {
            "level": "success",
            "insight": f"Upward trend (7-day average {delta:+.2f}). Nice work.",
            "suggestion": "Notice what has been helping and try to keep those habits going.",
        }
    if direction == "stable":
        return {
            "level": "info",
            "insight": "Your mood has been fairly stable this week.",
            "suggestion": "Consider journaling and reflecting on what influenced your day.",
        }
    return {
        "level": "info",
        "insight": "Not enough data for a trend yet.",
        "suggestion": "Check in daily for a week to start seeing patterns.",
    }


def aligned_daily(mood_points, sentiment_points):
    """Daily average mood and sentiment on the same dates (for the mood vs sentiment chart)."""
    m, s = daily_means(mood_points), daily_means(sentiment_points)
    days = sorted(set(m) | set(s))
    return {
        "labels": [f"{d:%d %b}" for d in days],
        "mood": [round(m[d], 2) if d in m else None for d in days],
        "sentiment": [round(s[d], 3) if d in s else None for d in days],
    }
