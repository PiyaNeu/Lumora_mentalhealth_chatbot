from datetime import date

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ChatbotWebsite import db
from ChatbotWebsite.auth.utils import public_url
from ChatbotWebsite.consultation import khalti
from ChatbotWebsite.consultation.booking import (BookingError, available_slots, ensure_demo_psychiatrists,
                                                 validate_booking)
from ChatbotWebsite.models import Appointment, Psychiatrist
from ChatbotWebsite.utils import local_now

consultation = Blueprint("consultation", __name__)

STATUS_COLORS = {"paid": "#2e9d5b", "cash_on_visit": "#e0a100", "unpaid": "#d64545"}


def _owned_appointment(appt_id):
    appt = db.session.get(Appointment, appt_id)
    if appt is None or appt.user_id != current_user.id:
        abort(404)
    return appt


@consultation.route("/")
@login_required
def index():
    ensure_demo_psychiatrists()
    doctors = Psychiatrist.query.filter_by(active=True).all()
    upcoming = (Appointment.query.filter(Appointment.user_id == current_user.id, Appointment.status != "cancelled",
                                         Appointment.date >= local_now().date())
                .order_by(Appointment.date, Appointment.time).all())
    return render_template("consultation/index.html", title="Consultation", doctors=doctors, upcoming=upcoming,
                           fee=current_app.config["CONSULTATION_FEE_NPR"], today=local_now().date(),
                           khalti_live=khalti.is_configured())


@consultation.route("/slots")
@login_required
def slots():
    doc = db.session.get(Psychiatrist, request.args.get("doctor", type=int) or 0)
    try:
        day = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        return jsonify({"slots": [], "error": "Invalid date"}), 400
    if doc is None:
        return jsonify({"slots": [], "error": "Unknown psychiatrist"}), 404
    return jsonify({"slots": available_slots(doc, day, local_now())})


@consultation.route("/book", methods=["POST"])
@login_required
def book():
    doc = db.session.get(Psychiatrist, request.form.get("doctor", type=int) or 0)
    method = (request.form.get("method") or "").strip().lower()
    try:
        day, time = validate_booking(doc, request.form.get("date"), request.form.get("time"), method, local_now())
    except BookingError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("consultation.index"))

    appt = Appointment(user_id=current_user.id, psychiatrist_id=doc.id, date=day, time=time,
                       payment_method=method, fee_npr=current_app.config["CONSULTATION_FEE_NPR"],
                       payment_status="cash_on_visit" if method == "cash" else "unpaid")
    db.session.add(appt)
    try:
        db.session.commit()
    except IntegrityError:  # two people grabbed the same slot at the same moment
        db.session.rollback()
        flash("Sorry, that slot was just booked. Please choose another time.", "danger")
        return redirect(url_for("consultation.index"))

    if method == "khalti":
        return redirect(url_for("consultation.pay", appt_id=appt.id))
    flash(f"Booked with {doc.name} on {day:%d %b} at {time}. Please pay at the clinic.", "success")
    return redirect(url_for("consultation.checkout", appt_id=appt.id))


@consultation.route("/appointments/<int:appt_id>/pay")
@login_required
def pay(appt_id):
    appt = _owned_appointment(appt_id)
    if appt.payment_status == "paid" or appt.status == "cancelled":
        return redirect(url_for("consultation.checkout", appt_id=appt.id))
    if not khalti.is_configured():
        # No sandbox key: show the clearly-labelled local demo checkout (report screenshot)
        return redirect(url_for("consultation.checkout", appt_id=appt.id))
    try:
        pidx, payment_url = khalti.initiate(
            appt.fee_npr, f"LUMORA-{appt.id}", f"Consultation with {appt.psychiatrist.name}",
            return_url=public_url("consultation.khalti_return"), website_url=current_app.config["PUBLIC_BASE_URL"],
            customer={"name": current_user.username, "email": current_user.email})
    except khalti.KhaltiError as exc:
        current_app.logger.error("Khalti initiate failed: %s", exc)
        flash("Couldn't start the Khalti payment. Please try again or choose cash on visit.", "danger")
        return redirect(url_for("consultation.checkout", appt_id=appt.id))
    appt.khalti_pidx = pidx
    db.session.commit()
    return redirect(payment_url)


@consultation.route("/khalti/return")
@login_required
def khalti_return():
    """Khalti redirects here after payment. Never trust the query string — verify with lookup."""
    pidx = request.args.get("pidx", "")
    appt = Appointment.query.filter_by(khalti_pidx=pidx, user_id=current_user.id).first() if pidx else None
    if appt is None:
        abort(404)
    try:
        record = khalti.lookup(pidx)
    except khalti.KhaltiError as exc:
        current_app.logger.error("Khalti lookup failed: %s", exc)
        flash("We couldn't confirm the payment with Khalti yet. Please refresh in a moment.", "warning")
        return redirect(url_for("consultation.checkout", appt_id=appt.id))
    if record.get("status") == "Completed" and int(record.get("total_amount", 0)) == appt.fee_npr * 100:
        appt.payment_status = "paid"
        appt.transaction_id = record.get("transaction_id")
        db.session.commit()
        flash("Payment confirmed. See you at your appointment!", "success")
    else:
        flash(f"Payment not completed (status: {record.get('status', 'unknown')}).", "warning")
    return redirect(url_for("consultation.checkout", appt_id=appt.id))


@consultation.route("/appointments/<int:appt_id>/demo-pay", methods=["POST"])
@login_required
def demo_pay(appt_id):
    """Local demo checkout, available only when no Khalti key is configured."""
    if khalti.is_configured():
        abort(404)
    appt = _owned_appointment(appt_id)
    if appt.status != "cancelled" and appt.payment_method == "khalti" and appt.payment_status == "unpaid":
        appt.payment_method, appt.payment_status = "khalti-demo", "paid"
        db.session.commit()
        flash("Demo payment recorded (no real money was taken).", "info")
    return redirect(url_for("consultation.checkout", appt_id=appt.id))


@consultation.route("/appointments/<int:appt_id>")
@login_required
def checkout(appt_id):
    return render_template("consultation/checkout.html", title="Checkout", appt=_owned_appointment(appt_id),
                           khalti_live=khalti.is_configured())


@consultation.route("/appointments/<int:appt_id>/cancel", methods=["POST"])
@login_required
def cancel(appt_id):
    appt = _owned_appointment(appt_id)
    appt.status = "cancelled"
    db.session.commit()
    flash("Appointment cancelled." + (" Contact the clinic about your refund." if appt.payment_status == "paid"
                                      else ""), "info")
    return redirect(url_for("consultation.index"))


@consultation.route("/calendar.json")
@login_required
def calendar_events():
    """The user's appointments as calendar events, coloured by payment status."""
    events = []
    for a in Appointment.query.filter(Appointment.user_id == current_user.id, Appointment.status != "cancelled"):
        events.append({
            "title": f"{a.time} {a.psychiatrist.name}",
            "start": f"{a.date.isoformat()}T{a.time}",
            "color": STATUS_COLORS[a.payment_status],
            "url": url_for("consultation.checkout", appt_id=a.id),
            "extendedProps": {"status": a.payment_status},
        })
    return jsonify(events)
