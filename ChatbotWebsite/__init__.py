from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from ChatbotWebsite.config import Config

# --- Initialize extensions globally ---
db = SQLAlchemy()
bcrypt = Bcrypt()
mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.debug:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # --- Initialize extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    # --- Import models after db is initialized ---
    from ChatbotWebsite import models

    # --- Register blueprints ---
    from ChatbotWebsite.main.routes import main
    from ChatbotWebsite.auth.routes import auth
    from ChatbotWebsite.chat.routes import chat
    from ChatbotWebsite.mood.routes import mood
    from ChatbotWebsite.journal.routes import journal
    from ChatbotWebsite.community.routes import community
    from ChatbotWebsite.selfhelp.routes import selfhelp
    from ChatbotWebsite.consultation.routes import consultation
    from ChatbotWebsite.evaluation.routes import evaluation
    from ChatbotWebsite.account.routes import account
    from ChatbotWebsite.errors.handlers import errors

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(chat)
    app.register_blueprint(mood, url_prefix="/mood")
    app.register_blueprint(journal, url_prefix="/journal")
    app.register_blueprint(community, url_prefix="/community")
    app.register_blueprint(selfhelp, url_prefix="/selfhelp")
    app.register_blueprint(consultation, url_prefix="/consultation")
    app.register_blueprint(evaluation, url_prefix="/evaluation")
    app.register_blueprint(account, url_prefix="/account")
    app.register_blueprint(errors)

    # --- Flask-Admin (staff only) ---
    class AdminModelView(ModelView):
        def is_accessible(self):
            return current_user.is_authenticated and getattr(current_user, "is_admin", False)

        def inaccessible_callback(self, name, **kwargs):
            return redirect(url_for("auth.login"))

    admin = Admin(app, name="Lumora Admin")
    admin.add_view(AdminModelView(models.User, db.session, endpoint="admin_user"))
    admin.add_view(AdminModelView(models.Journal, db.session, endpoint="admin_journal"))
    admin.add_view(AdminModelView(models.ChatMessage, db.session, endpoint="admin_chatmessage"))

    # --- Create tables (SQLite, no migrations) ---
    with app.app_context():
        db.create_all()

    return app
