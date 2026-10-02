import os
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from PIL import Image

from ChatbotWebsite import bcrypt, db
from ChatbotWebsite.account.export import build_user_export
from ChatbotWebsite.account.forms import AccountForm
from ChatbotWebsite.chat.service import delete_messages_before, delete_sessions
from ChatbotWebsite import models
from ChatbotWebsite.models import ChatSession, Journal, MoodEntry
from ChatbotWebsite.utils import local_today

account = Blueprint("account", __name__)

# "Delete data older than…" choices. None = everything.
WINDOWS = {"1w": ("Older than 1 week", 7), "1m": ("Older than 1 month", 30), "3m": ("Older than 3 months", 90),
           "6m": ("Older than 6 months", 180), "all": ("Everything", None)}


def _cutoff(window_key):
    if window_key not in WINDOWS:
        abort(400)
    days = WINDOWS[window_key][1]
    # "Everything" = anything created before a moment slightly in the future
    return datetime.utcnow() + timedelta(seconds=1) if days is None else datetime.utcnow() - timedelta(days=days)


def _save_picture(file_storage):
    """Store a 250x250 copy under a random name; return the file name."""
    name = secrets.token_hex(8) + ".jpg"
    path = os.path.join(current_app.static_folder, "profile_images", name)
    img = Image.open(file_storage)
    img = img.convert("RGB")
    img.thumbnail((250, 250))
    img.save(path, "JPEG", quality=85)
    return name


@account.route("/", methods=["GET", "POST"])
@login_required
def profile():
    form = AccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            old = current_user.profile_image
            current_user.profile_image = _save_picture(form.picture.data)
            if old and old != "default.jpg":
                try:
                    os.remove(os.path.join(current_app.static_folder, "profile_images", old))
                except OSError:
                    pass
        current_user.username = form.username.data.strip()
        current_user.preferred_mode = form.preferred_mode.data
        db.session.commit()
        flash("Your account has been updated.", "success")
        return redirect(url_for("account.profile"))
    if request.method == "GET":
        form.username.data = current_user.username
        form.preferred_mode.data = current_user.preferred_mode
    return render_template("account/profile.html", title="Account", form=form)


@account.route("/privacy")
@login_required
def privacy():
    sessions = (ChatSession.query.filter_by(user_id=current_user.id)
                .order_by(ChatSession.updated_at.desc()).all())
    return render_template("account/privacy.html", title="Privacy & Data Controls", windows=WINDOWS,
                           sessions=sessions)


@account.route("/privacy/delete-messages", methods=["POST"])
@login_required
def delete_messages():
    n = delete_messages_before(current_user.id, _cutoff(request.form.get("window")))
    db.session.commit()
    flash(f"Deleted {n} chat message{'s' if n != 1 else ''}.", "info")
    return redirect(url_for("account.privacy"))


@account.route("/privacy/delete-moods", methods=["POST"])
@login_required
def delete_moods():
    n = MoodEntry.query.filter(MoodEntry.user_id == current_user.id,
                               MoodEntry.created_at < _cutoff(request.form.get("window"))).delete()
    db.session.commit()
    flash(f"Deleted {n} mood log{'s' if n != 1 else ''}.", "info")
    return redirect(url_for("account.privacy"))


@account.route("/privacy/delete-journals", methods=["POST"])
@login_required
def delete_journals():
    n = Journal.query.filter(Journal.user_id == current_user.id,
                             Journal.date_created < _cutoff(request.form.get("window"))).delete()
    db.session.commit()
    flash(f"Deleted {n} journal entr{'ies' if n != 1 else 'y'}.", "info")
    return redirect(url_for("account.privacy"))


@account.route("/privacy/delete-conversation", methods=["POST"])
@login_required
def delete_conversation():
    s = db.session.get(ChatSession, request.form.get("session_id", type=int) or 0)
    if s is None or s.user_id != current_user.id:
        flash("Please choose one of your conversations.", "warning")
        return redirect(url_for("account.privacy"))
    delete_sessions([s])
    db.session.commit()
    flash("Conversation deleted.", "info")
    return redirect(url_for("account.privacy"))


@account.route("/privacy/delete-all-conversations", methods=["POST"])
@login_required
def delete_all_conversations():
    if request.form.get("confirm") != "DELETE":
        flash('Type DELETE to confirm deleting all conversations.', "warning")
        return redirect(url_for("account.privacy"))
    n = delete_sessions(ChatSession.query.filter_by(user_id=current_user.id).all())
    db.session.commit()
    flash(f"All conversations deleted ({n} messages).", "info")
    return redirect(url_for("account.privacy"))


@account.route("/privacy/export.pdf")
@login_required
def export_data():
    resp = make_response(build_user_export(current_user))
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename=Lumora_My_Data-{local_today():%Y-%m-%d}.pdf"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def delete_user_data(user):
    """Remove the user and everything they own. Caller commits."""
    uid = user.id
    delete_sessions(ChatSession.query.filter_by(user_id=uid).all())
    for model in (models.MoodEntry, models.Journal, models.SavedInsight, models.CrisisEvent,
                  models.AssessmentResult, models.ToolUsage, models.SentimentLabel, models.SessionFeedback,
                  models.Appointment, models.CommunityReaction, models.CommunityReport, models.CommunityComment):
        model.query.filter_by(user_id=uid).delete()
    for post in models.CommunityPost.query.filter_by(user_id=uid).all():
        models.CommunityReport.query.filter_by(target_type="post", target_id=post.id).delete()
        db.session.delete(post)
    models.ChatMessage.query.filter_by(user_id=uid).delete()
    if user.profile_image and user.profile_image != "default.jpg":
        try:
            os.remove(os.path.join(current_app.static_folder, "profile_images", user.profile_image))
        except OSError:
            pass
    db.session.delete(user)


@account.route("/delete", methods=["POST"])
@login_required
def delete_account():
    if not bcrypt.check_password_hash(current_user.password, request.form.get("password", "")):
        flash("Password incorrect — your account was not deleted.", "danger")
        return redirect(url_for("account.profile"))
    user = db.session.get(models.User, current_user.id)
    logout_user()
    delete_user_data(user)
    db.session.commit()
    flash("Your account and all your data have been deleted.", "info")
    return redirect(url_for("main.home"))

