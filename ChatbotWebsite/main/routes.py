from flask import Blueprint, render_template

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
    pending = any(display_phone(h) is None for h in HOTLINES + EMERGENCY)
    return render_template("sos.html", title="SOS", hotlines=HOTLINES, emergency=EMERGENCY,
                           display_phone=display_phone, pending=pending)
