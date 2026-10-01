"""Slot generation and booking validation for consultations."""
from datetime import date, datetime, timedelta

from ChatbotWebsite import db
from ChatbotWebsite.models import Appointment, Psychiatrist

BOOKING_WINDOW_DAYS = 60
ALLOWED_METHODS = ("khalti", "cash")

DEMO_PSYCHIATRISTS = [
    dict(name="Dr. Asha Shrestha", specialty="Anxiety, Depression", location="Kathmandu",
         languages="Nepali, English", work_days="0,1,2,3,4", start_time="16:00", end_time="20:00",
         bio="Focuses on CBT-based care and medication management."),
    dict(name="Dr. Rohan KC", specialty="Stress, Burnout, Sleep", location="Lalitpur",
         languages="Nepali, English, Hindi", work_days="6,0,1,2,3", start_time="10:00", end_time="14:00",
         bio="Works with students and young adults; burnout and sleep hygiene."),
    dict(name="Dr. Mira Gurung", specialty="Trauma, PTSD", location="Online",
         languages="English, Nepali", work_days="0,1,2,3,4,5,6", start_time="10:00", end_time="16:00",
         bio="Trauma-informed care, supportive counselling and referrals when needed."),
]


def ensure_demo_psychiatrists():
    """Seed the demo profiles (report screenshots) if the table is empty."""
    if Psychiatrist.query.count() == 0:
        db.session.add_all(Psychiatrist(is_demo=True, **d) for d in DEMO_PSYCHIATRISTS)
        db.session.commit()


def _parse_hm(value):
    return datetime.strptime(value, "%H:%M").time()


def all_slots(doc, day):
    """Every slot start time ("HH:MM") the doctor offers on `day` (ignores bookings)."""
    if str(day.weekday()) not in doc.work_days.split(","):
        return []
    start = datetime.combine(day, _parse_hm(doc.start_time))
    end = datetime.combine(day, _parse_hm(doc.end_time))
    slots, t = [], start
    while t + timedelta(minutes=doc.slot_minutes) <= end:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=doc.slot_minutes)
    return slots


def booked_times(doc_id, day):
    return {a.time for a in Appointment.query.filter(Appointment.psychiatrist_id == doc_id,
                                                     Appointment.date == day,
                                                     Appointment.status != "cancelled")}


def available_slots(doc, day, now_local):
    """Slots that are offered, not booked and still in the future."""
    taken = booked_times(doc.id, day)
    return [s for s in all_slots(doc, day)
            if s not in taken and datetime.combine(day, _parse_hm(s)) > now_local]


class BookingError(ValueError):
    pass


def validate_booking(doc, day_str, time_str, method, now_local):
    """Return (day, time) or raise BookingError with a user-facing message."""
    if doc is None or not doc.active:
        raise BookingError("Please choose a psychiatrist.")
    if not method:
        raise BookingError("Please choose a payment method.")
    if method not in ALLOWED_METHODS:
        raise BookingError("That payment method isn't supported. Choose Khalti or cash on visit.")
    try:
        day = date.fromisoformat(day_str or "")
        _parse_hm(time_str or "")
    except ValueError:
        raise BookingError("Please choose a valid date and time.")
    if day < now_local.date() or day > now_local.date() + timedelta(days=BOOKING_WINDOW_DAYS):
        raise BookingError(f"Bookings can be made up to {BOOKING_WINDOW_DAYS} days ahead.")
    if time_str not in all_slots(doc, day):
        raise BookingError(f"{doc.name} isn't available at that time. Please pick one of the listed slots.")
    if datetime.combine(day, _parse_hm(time_str)) <= now_local:
        raise BookingError("That time has already passed.")
    if time_str in booked_times(doc.id, day):
        raise BookingError("Sorry, that slot was just booked. Please choose another time.")
    return day, time_str
