"""Small shared helpers."""
from datetime import datetime, timedelta

from flask import current_app


def _offset():
    return timedelta(minutes=current_app.config["UTC_OFFSET_MINUTES"])


def local_now():
    """Current local time (naive), e.g. Nepal time. Stored timestamps stay UTC."""
    return datetime.utcnow() + _offset()


def to_local(dt):
    return dt + _offset() if dt is not None else None


def local_today():
    return local_now().date()
