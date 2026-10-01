from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from ChatbotWebsite.config import Config

# --- Initialize extensions globally ---
db = SQLAlchemy()
bcrypt = Bcrypt()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'users.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.static_folder = 'static'

    # --- Enable template auto-reload ---
    app.debug = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    # --- Cache-busting for static files ---
    @app.context_processor
    def override_url_for():
        from flask import url_for
        import time
        return dict(url_for=lambda endpoint, **values: url_for(endpoint, **values, v=int(time.time())))

    # --- Initialize extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # --- Import models after db is initialized ---
    from ChatbotWebsite.models import User, Journal, ChatMessage

    # --- Register blueprints ---
    from ChatbotWebsite.main.routes import main
    from ChatbotWebsite.chatbot.routes import chatbot
    #from ChatbotWebsite.users.routes import users
    from ChatbotWebsite.errors.handlers import errors
    #from ChatbotWebsite.journal.routes import journals

    #app.register_blueprint(users)
    app.register_blueprint(chatbot)
    app.register_blueprint(main)
    app.register_blueprint(errors)
    #app.register_blueprint(journals)

    # --- Flask-Admin setup ---
    class AdminModelView(ModelView):
        def is_accessible(self):
            return current_user.is_authenticated and getattr(current_user, "is_admin", False)

        def inaccessible_callback(self, name, **kwargs):
            return redirect(url_for("users.login"))

    admin = Admin(app, name="Lumora Admin")
    admin.add_view(AdminModelView(User, db.session))
    admin.add_view(AdminModelView(Journal, db.session))
    admin.add_view(AdminModelView(ChatMessage, db.session))

    return app
