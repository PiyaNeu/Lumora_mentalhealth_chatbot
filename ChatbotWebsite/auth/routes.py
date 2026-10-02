from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from ChatbotWebsite import bcrypt, db
from ChatbotWebsite.auth.forms import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from ChatbotWebsite.auth.utils import send_reset_email, send_verification_email
from ChatbotWebsite.models import User

auth = Blueprint("auth", __name__)


def _safe_next(target):
    """Only allow relative redirects (prevents open redirects via ?next=)."""
    if target and not urlparse(target).netloc and target.startswith("/"):
        return target
    return None


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            password=bcrypt.generate_password_hash(form.password.data).decode("utf-8"),
        )
        db.session.add(user)
        db.session.commit()
        if send_verification_email(user):
            flash("Account created! Check your email to verify your account before logging in.", "success")
        else:
            flash("Account created, but the verification email could not be sent. "
                  "Use 'Resend verification' on the login page.", "warning")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", title="Register", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if not user or not bcrypt.check_password_hash(user.password, form.password.data):
            flash("Login unsuccessful. Please check email and password.", "danger")
        elif not user.is_verified:
            session["unverified_email"] = user.email
            flash("Please verify your email before logging in.", "warning")
        else:
            session.pop("guest", None)
            login_user(user, remember=form.remember_me.data)
            return redirect(_safe_next(request.args.get("next")) or url_for("main.home"))
    return render_template("auth/login.html", title="Login", form=form,
                           unverified_email=session.get("unverified_email"))


@auth.route("/logout")
def logout():
    logout_user()
    lang = session.get("ui_lang")
    session.clear()
    if lang:
        session["ui_lang"] = lang  # keep the interface language after logout
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth.route("/guest")
def guest():
    """Guest mode: chat without an account. Nothing is persisted for guests."""
    if current_user.is_authenticated:
        logout_user()
    lang = session.get("ui_lang")
    session.clear()
    session["guest"] = True
    if lang:
        session["ui_lang"] = lang
    flash("You're chatting as a guest. Your conversation won't be saved.", "info")
    return redirect(url_for("chat.chat_page"))


@auth.route("/verify/<token>")
def verify_email(token):
    user = User.verify_confirmation_token(token)
    if user is None:
        flash("That verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))
    if not user.is_verified:
        user.is_verified = True
        db.session.commit()
    session.pop("unverified_email", None)
    flash("Your email has been verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = session.get("unverified_email")
    user = User.query.filter_by(email=email).first() if email else None
    if user and not user.is_verified:
        if send_verification_email(user):
            flash("A new verification email has been sent.", "info")
        else:
            flash("The verification email could not be sent. Please try again later.", "danger")
    return redirect(url_for("auth.login"))


@auth.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user:
            send_reset_email(user)
        # Same message either way so the form can't be used to discover accounts
        flash("If that email is registered, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html", title="Reset Password", form=form)


@auth.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    user = User.verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired.", "warning")
        return redirect(url_for("auth.reset_request"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        db.session.commit()
        flash("Your password has been updated. You can now log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_token.html", title="Reset Password", form=form)

