"""Psychiatrist booking, calendar and payment — mirrors report Tables 4.4.11 (TC-L1…L4) and 4.4.12 (TC-M1…M3)."""
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from ChatbotWebsite import db
from ChatbotWebsite.consultation import khalti
from ChatbotWebsite.consultation.booking import ensure_demo_psychiatrists
from ChatbotWebsite.models import Appointment, Psychiatrist
from tests.test_chat_sessions import login_user_


def next_weekday(weekday, min_days=2):
    d = date.today() + timedelta(days=min_days)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


@pytest.fixture
def asha(app):
    ensure_demo_psychiatrists()
    return Psychiatrist.query.filter_by(name="Dr. Asha Shrestha").one()  # Mon–Fri 16:00–20:00


def book(client, doc, day, time="16:30", method="cash"):
    return client.post("/consultation/book", data={"doctor": doc.id, "date": day.isoformat(), "time": time,
                                                   "method": method}, follow_redirects=True)


# TC-L1: psychiatrist list
def test_view_psychiatrist_list(client):
    login_user_(client)
    page = client.get("/consultation/").data
    for name in (b"Dr. Asha Shrestha", b"Dr. Rohan KC", b"Dr. Mira Gurung"):
        assert name in page
    assert b"Demo profile" in page and b"NPR 1500" in page


# TC-L2: book a valid slot
def test_book_valid_slot(client, asha):
    login_user_(client)
    day = next_weekday(0)
    resp = book(client, asha, day)
    assert b"Booked with Dr. Asha Shrestha" in resp.data
    a = Appointment.query.one()
    assert (a.time, a.payment_method, a.payment_status, a.fee_npr) == ("16:30", "cash", "cash_on_visit", 1500)


# TC-L3: double booking prevented
def test_double_booking_prevented(client, asha):
    login_user_(client)
    day = next_weekday(0)
    book(client, asha, day)
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    resp = book(client, asha, day)
    assert b"just booked" in resp.data
    assert Appointment.query.count() == 1


def test_database_blocks_double_booking_even_without_app_check(app, asha):
    user = login_user_(app.test_client())
    day = next_weekday(1)
    db.session.add(Appointment(user_id=user.id, psychiatrist_id=asha.id, date=day, time="17:00",
                               payment_method="cash", payment_status="cash_on_visit", fee_npr=1500))
    db.session.commit()
    db.session.add(Appointment(user_id=user.id, psychiatrist_id=asha.id, date=day, time="17:00",
                               payment_method="cash", payment_status="cash_on_visit", fee_npr=1500))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# TC-L4: calendar shows unavailable (booked) slots
def test_booked_slot_unavailable_and_shown_on_calendar(client, asha):
    login_user_(client)
    day = next_weekday(2)
    before = client.get(f"/consultation/slots?doctor={asha.id}&date={day}").get_json()["slots"]
    assert "16:30" in before and before[0] == "16:00" and before[-1] == "19:30"
    book(client, asha, day)
    after = client.get(f"/consultation/slots?doctor={asha.id}&date={day}").get_json()["slots"]
    assert "16:30" not in after and len(after) == len(before) - 1
    events = client.get("/consultation/calendar.json").get_json()
    assert events[0]["start"] == f"{day.isoformat()}T16:30"
    assert events[0]["extendedProps"]["status"] == "cash_on_visit"


def test_cancel_frees_slot(client, asha):
    login_user_(client)
    day = next_weekday(3)
    book(client, asha, day)
    appt = Appointment.query.one()
    client.post(f"/consultation/appointments/{appt.id}/cancel")
    assert "16:30" in client.get(f"/consultation/slots?doctor={asha.id}&date={day}").get_json()["slots"]
    assert b"Booked" in book(client, asha, day).data  # can rebook the cancelled slot


@pytest.mark.parametrize("day_offset,time,msg", [
    (None, "09:00", b"available at that time"),   # outside working hours
    (-3, "16:30", b"up to 60 days"),                     # in the past
    (90, "16:30", b"up to 60 days"),                     # too far ahead
])
def test_invalid_slots_rejected(client, asha, day_offset, time, msg):
    login_user_(client)
    day = next_weekday(0) if day_offset is None else date.today() + timedelta(days=day_offset)
    assert msg in book(client, asha, day, time).data
    assert Appointment.query.count() == 0


def test_closed_day_has_no_slots(client, asha):
    login_user_(client)
    saturday = next_weekday(5)
    assert client.get(f"/consultation/slots?doctor={asha.id}&date={saturday}").get_json()["slots"] == []


def test_users_cannot_see_others_appointments(client, asha):
    login_user_(client)
    book(client, asha, next_weekday(0))
    appt_id = Appointment.query.one().id
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.get(f"/consultation/appointments/{appt_id}").status_code == 404
    assert client.get("/consultation/calendar.json").get_json() == []


# TC-M1: valid Khalti payment is initiated (sandbox API mocked)
def test_khalti_payment_initiated(client, app, asha, monkeypatch):
    app.config["KHALTI_SECRET_KEY"] = "test_secret_key"
    calls = {}

    def fake_initiate(amount, order_id, name, return_url, website_url, customer=None):
        calls.update(amount=amount, order_id=order_id, return_url=return_url)
        return "pidx123", "https://test-pay.khalti.com/?pidx=pidx123"

    monkeypatch.setattr(khalti, "initiate", fake_initiate)
    login_user_(client)
    resp = client.post("/consultation/book", data={"doctor": asha.id, "date": next_weekday(0).isoformat(),
                                                    "time": "18:00", "method": "khalti"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/pay")
    resp = client.get(resp.headers["Location"])
    assert resp.headers["Location"] == "https://test-pay.khalti.com/?pidx=pidx123"
    appt = Appointment.query.one()
    assert appt.khalti_pidx == "pidx123" and appt.payment_status == "unpaid"
    assert calls["amount"] == 1500 and calls["return_url"] == "http://localhost/consultation/khalti/return"


@pytest.mark.parametrize("record,expected", [
    ({"status": "Completed", "total_amount": 150000, "transaction_id": "T1"}, "paid"),
    ({"status": "Pending", "total_amount": 150000}, "unpaid"),
    ({"status": "Completed", "total_amount": 1000}, "unpaid"),   # wrong amount is never accepted
])
def test_khalti_return_verified_with_lookup(client, app, asha, monkeypatch, record, expected):
    app.config["KHALTI_SECRET_KEY"] = "test_secret_key"
    monkeypatch.setattr(khalti, "initiate", lambda *a, **k: ("pidx9", "https://pay.example/"))
    monkeypatch.setattr(khalti, "lookup", lambda pidx: record)
    login_user_(client)
    client.post("/consultation/book", data={"doctor": asha.id, "date": next_weekday(1).isoformat(),
                                            "time": "18:00", "method": "khalti"})
    client.get(f"/consultation/appointments/{Appointment.query.one().id}/pay")
    # Query-string status is ignored: only lookup decides
    client.get("/consultation/khalti/return?pidx=pidx9&status=Completed")
    assert Appointment.query.one().payment_status == expected


# TC-M2: missing payment method
def test_missing_payment_method_rejected(client, asha):
    login_user_(client)
    assert b"choose a payment method" in book(client, asha, next_weekday(0), method="").data
    assert Appointment.query.count() == 0


# TC-M3: invalid method (card) rejected
def test_card_payment_rejected(client, asha):
    login_user_(client)
    assert b"method isn&#39;t supported" in book(client, asha, next_weekday(0), method="card").data
    assert Appointment.query.count() == 0


def test_demo_checkout_only_without_key(client, app, asha):
    login_user_(client)
    client.post("/consultation/book", data={"doctor": asha.id, "date": next_weekday(4).isoformat(),
                                            "time": "16:00", "method": "khalti"})
    appt = Appointment.query.one()
    page = client.get(f"/consultation/appointments/{appt.id}").data
    assert b"local demo checkout" in page
    client.post(f"/consultation/appointments/{appt.id}/demo-pay")
    db.session.refresh(appt)
    assert (appt.payment_method, appt.payment_status) == ("khalti-demo", "paid")
    app.config["KHALTI_SECRET_KEY"] = "configured"
    assert client.post(f"/consultation/appointments/{appt.id}/demo-pay").status_code == 404


def test_consultation_requires_login(client):
    assert client.get("/consultation/").status_code == 302
