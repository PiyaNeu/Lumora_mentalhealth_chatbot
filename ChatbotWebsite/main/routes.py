from urllib.parse import urlparse

from flask import Blueprint, redirect, render_template, request, session, url_for

from ChatbotWebsite.i18n import LANGUAGES

from ChatbotWebsite.sos_config import EMERGENCY, HOTLINES, display_phone

main = Blueprint("main", __name__)


# Home Page
@main.route("/")
def home():
    return render_template("home.html", title="Lumora AI")

@main.route("/about")
def about():
    return render_template("about.html", title="About")

@main.route("/sos")
def sos():
    # The chat's crisis redirect passes ?lang=ne for Nepali messages so help is shown in Nepali
    if request.args.get("lang") in LANGUAGES:
        session["ui_lang"] = request.args["lang"]
    pending = any(display_phone(h) is None for h in HOTLINES + EMERGENCY)
    return render_template("sos.html", title="SOS", hotlines=HOTLINES, emergency=EMERGENCY,
                           display_phone=display_phone, pending=pending)


@main.route("/lang/<code>")
def set_language(code):
    """EN | ने toggle. Returns to the page the user was on (same site only)."""
    if code in LANGUAGES:
        session["ui_lang"] = code
    ref = urlparse(request.referrer or "")
    if ref.netloc == request.host and ref.path:
        return redirect(ref.path + (f"?{ref.query}" if ref.query else ""))
    return redirect(url_for("main.home"))

