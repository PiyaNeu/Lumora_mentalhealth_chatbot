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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Chat response style: auto | listener | coach | therapist | balanced
    preferred_mode = db.Column(db.String(20), nullable=False, default="auto", server_default="auto")
    messages = db.relationship('ChatMessage', backref='user', lazy=True)
    journals = db.relationship('Journal', backref='user', lazy=True)

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


# Journal mood tags and where they sit on the 1–5 mood scale
JOURNAL_MOODS = {
    "Happy": ("😊", 5), "Grateful": ("🙏", 5), "Calm": ("😌", 4), "Hopeful": ("🌱", 4),
    "Okay": ("😐", 3), "Tired": ("😴", 2), "Stressed": ("😣", 2), "Anxious": ("😟", 2),
    "Sad": ("😢", 2), "Angry": ("😠", 2), "Lonely": ("🥺", 2), "Awful": ("😞", 1),
}


class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_at = db.Column(db.DateTime)
    mood_tag = db.Column(db.String(20))          # e.g. Happy, Sad (see JOURNAL_MOODS)
    mood = db.Column(db.Integer)                 # mood_tag mapped to the 1–5 mood scale
    sentiment_compound = db.Column(db.Float)
    sentiment_score = db.Column(db.Float)
    sentiment_label = db.Column(db.String(10))

    def __repr__(self):
        return f'Journal({self.title}, user_id={self.user_id})'


class ChatSession(db.Model):
    """One conversation in "Your Chats" (logged-in users only; guest chats are never stored)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(80), nullable=False, default="New Chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    messages = db.relationship('ChatMessage', backref='session', lazy=True,
                               cascade="all, delete-orphan", order_by="ChatMessage.id")

    def __repr__(self):
        return f'ChatSession(id={self.id}, user_id={self.user_id}, title="{self.title}")'


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), index=True)
    role = db.Column(db.String(10), nullable=False, default="user", server_default="user")  # user | bot
    # Pipeline metadata (bot messages): which route produced the reply
    route = db.Column(db.String(20))        # sos | medium_risk | guard | intent | llm | fallback
    intent = db.Column(db.String(60))
    confidence = db.Column(db.Float)
    strategy = db.Column(db.String(20))
    language = db.Column(db.String(10))     # en | ne | ne-rom
    risk_level = db.Column(db.String(10))   # none | medium | high
    # Sentiment (user messages, logged-in only): VADER compound + hybrid score/label
    sentiment_compound = db.Column(db.Float)
    sentiment_score = db.Column(db.Float)
    sentiment_label = db.Column(db.String(10))  # negative | neutral | positive

    def to_dict(self):
        return {
            "id": self.id, "role": self.role, "text": self.message,
            "time": self.timestamp.strftime("%d/%m/%Y, %H:%M"),
            "route": self.route, "sos": self.route == "sos",
        }

    def __repr__(self):
        return f'ChatMessage(user_id={self.user_id}, role={self.role}, message="{self.message[:20]}")'


class SavedInsight(db.Model):
    """A bot reply the user chose to keep ("Save insight")."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id', ondelete="SET NULL"))
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id', ondelete="SET NULL"))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CrisisEvent(db.Model):
    """Log of risk-screening hits for logged-in users (ER diagram: Crisis Alert)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id', ondelete="SET NULL"))
    level = db.Column(db.String(10), nullable=False)  # medium | high
    matched = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


MOOD_LABELS = {1: "Terrible", 2: "Low", 3: "Neutral", 4: "Good", 5: "Excellent"}
MOOD_EMOJI = {1: "😢", 2: "😟", 3: "😐", 4: "🙂", 5: "😄"}


class MoodEntry(db.Model):
    """Mood on a 1–5 scale. source="Manual": one per user per local day (updated in place).
    source="Chat": derived from the sentiment of a chat message (report PDF screenshot)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    mood = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(300))
    source = db.Column(db.String(10), nullable=False, default="Manual")  # Manual | Chat
    day = db.Column(db.Date, nullable=False, index=True)  # local date
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id', ondelete="SET NULL"))

    @property
    def label(self):
        return MOOD_LABELS.get(self.mood, "")

    def __repr__(self):
        return f'MoodEntry(user_id={self.user_id}, day={self.day}, mood={self.mood}, source={self.source})'


class AssessmentResult(db.Model):
    """Saved self-test result (logged-in users). Used for history and J3 assessment change."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    test = db.Column(db.String(20), nullable=False)   # phq9 | gad7 | burnout
    score = db.Column(db.Integer, nullable=False)
    band = db.Column(db.String(30), nullable=False)
    answers = db.Column(db.String(200))               # comma-separated option values
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

