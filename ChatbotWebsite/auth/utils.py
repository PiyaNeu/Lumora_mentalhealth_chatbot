import smtplib

from flask import current_app, render_template, url_for
from flask_mail import Message

from ChatbotWebsite import mail


def public_url(endpoint, **values):
    """Absolute link built on PUBLIC_BASE_URL so emails work behind ngrok/Render."""
    return current_app.config["PUBLIC_BASE_URL"] + url_for(endpoint, **values)


def _send(subject, recipient, html):
    """Send an email. Returns True on success; logs and returns False otherwise.

    With MAIL_SUPPRESS_SEND, Flask-Mail records the message without sending it.
    Without SMTP credentials the email is only logged (useful for local demos).
    """
    cfg = current_app.config
    if not cfg.get("MAIL_SUPPRESS_SEND") and not cfg.get("MAIL_USERNAME"):
        current_app.logger.warning("Mail not configured; email to %s not sent:\n%s", recipient, html)
        return False
    msg = Message(subject, recipients=[recipient], html=html,
                  sender=cfg.get("MAIL_DEFAULT_SENDER") or "noreply@lumora.local")
    try:
        mail.send(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.error("Failed to send email to %s: %s", recipient, exc)
        return False


def send_verification_email(user):
    link = public_url("auth.verify_email", token=user.get_confirmation_token())
    html = render_template("email/verify_email.html", user=user, confirm_url=link)
    return _send("Verify your Lumora account", user.email, html)


def send_reset_email(user):
    link = public_url("auth.reset_token", token=user.get_reset_token())
    html = render_template("email/reset_password.html", user=user, reset_url=link)
    return _send("Reset your Lumora password", user.email, html)
