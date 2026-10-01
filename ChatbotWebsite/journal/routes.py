import random
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ChatbotWebsite import db
from ChatbotWebsite.chat.language import detect_language
from ChatbotWebsite.chat.translate import to_english
from ChatbotWebsite.journal.forms import JournalForm
from ChatbotWebsite.models import JOURNAL_MOODS, Journal
from ChatbotWebsite.sentiment import analyze, hybrid

journal = Blueprint("journal", __name__)

PER_PAGE = 6
PROMPTS = [
    "Right now I feel… because… What I need most is…",
    "One thing that was hard today, one thing that went okay, and one thing I'm grateful for.",
    "What took most of my energy today, and what gave me a little energy back?",
    "If a close friend had my day, what would I say to them?",
    "What is one worry I can let go of tonight, and one small step for tomorrow?",
    "Describe a moment today when you felt calm, even briefly.",
    "What am I proud of this week, however small?",
]


def _owned(journal_id):
    entry = db.session.get(Journal, journal_id)
    if entry is None or entry.user_id != current_user.id:
        abort(404)
    return entry


def _apply(entry, form):
    entry.mood_tag = form.mood_tag.data
    entry.mood = JOURNAL_MOODS[entry.mood_tag][1]
    entry.content = form.content.data.strip()
    entry.title = (form.title.data or "").strip() or f"Feeling {entry.mood_tag}"
    text_en = to_english(entry.content, detect_language(entry.content))
    entry.sentiment_compound = analyze(text_en).compound
    mood = hybrid(text_en)
    entry.sentiment_score, entry.sentiment_label = mood.score, mood.label


@journal.route("/")
@login_required
def all_journals():
    page = request.args.get("page", 1, type=int)
    journals = (Journal.query.filter_by(user_id=current_user.id)
                .order_by(Journal.date_created.desc())
                .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template("journal/list.html", title="Journals", journals=journals, moods=JOURNAL_MOODS)


@journal.route("/new", methods=["GET", "POST"])
@login_required
def new_journal():
    form = JournalForm()
    if form.validate_on_submit():
        entry = Journal(user_id=current_user.id)
        _apply(entry, form)
        db.session.add(entry)
        db.session.commit()
        flash("Your journal has been saved.", "success")
        return redirect(url_for("journal.view_journal", journal_id=entry.id))
    return render_template("journal/form.html", title="New Journal", form=form, legend="New Journal",
                           prompt=random.choice(PROMPTS))


@journal.route("/<int:journal_id>")
@login_required
def view_journal(journal_id):
    return render_template("journal/view.html", title="Journal", journal=_owned(journal_id),
                           moods=JOURNAL_MOODS)


@journal.route("/<int:journal_id>/edit", methods=["GET", "POST"])
@login_required
def edit_journal(journal_id):
    entry = _owned(journal_id)
    form = JournalForm()
    if form.validate_on_submit():
        _apply(entry, form)
        entry.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Your journal has been updated.", "success")
        return redirect(url_for("journal.view_journal", journal_id=entry.id))
    if request.method == "GET":
        form.mood_tag.data, form.title.data, form.content.data = entry.mood_tag, entry.title, entry.content
    return render_template("journal/form.html", title="Edit Journal", form=form, legend="Edit Journal",
                           prompt=None)


@journal.route("/<int:journal_id>/delete", methods=["POST"])
@login_required
def delete_journal(journal_id):
    db.session.delete(_owned(journal_id))
    db.session.commit()
    flash("Your journal has been deleted.", "info")
    return redirect(url_for("journal.all_journals"))
