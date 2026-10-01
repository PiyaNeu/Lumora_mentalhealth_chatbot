from datetime import datetime
from ChatbotWebsite import db, login_manager
from flask_login import UserMixin
from itsdangerous import BadSignature, URLSafeTimedSerializer as Serializer
from flask import current_app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _serializer():
    return Serializer(current_app.config["SECRET_KEY"])

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    profile_image = db.Column(db.String(20), nullable=False, default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    messages = db.relationship('ChatMessage', backref='user', lazy=True)
    journals = db.relationship('Journal', backref='user', lazy=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Separate salts so a verification token can't be used as a reset token
    def _token(self, purpose):
        salt = f"{current_app.config['SECURITY_PASSWORD_SALT']}-{purpose}"
        return _serializer().dumps({"user_id": self.id}, salt=salt)

    @staticmethod
    def _load_token(token, purpose, max_age):
        salt = f"{current_app.config['SECURITY_PASSWORD_SALT']}-{purpose}"
        try:
            user_id = _serializer().loads(token, salt=salt, max_age=max_age)["user_id"]
        except (BadSignature, KeyError, TypeError):  # BadSignature covers expiry
            return None
        return db.session.get(User, user_id)

    def get_confirmation_token(self):
        return self._token("verify")

    @staticmethod
    def verify_confirmation_token(token, expiration=86400):
        return User._load_token(token, "verify", expiration)

    def get_reset_token(self):
        return self._token("reset")

    @staticmethod
    def verify_reset_token(token, expiration=1800):
        return User._load_token(token, "reset", expiration)

    def __repr__(self):
        return f'User({self.username}, {self.email}, verified={self.is_verified})'


class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'Journal({self.title}, user_id={self.user_id})'


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'ChatMessage(user_id={self.user_id}, message="{self.message[:20]}")'
