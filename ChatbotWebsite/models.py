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


class ToolUsage(db.Model):
    """Lightweight log of self-help tool use (e.g. mindfulness plays) for J3 engagement metrics."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    tool = db.Column(db.String(30), nullable=False)    # e.g. mindfulness
    detail = db.Column(db.String(60))                   # e.g. exercise id
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


COMMUNITY_TAGS = ("anxiety", "exams", "relationship", "sadness", "sleep", "stress")
REACTIONS = ("support", "relate", "heart")


class CommunityPost(db.Model):
    """Anonymous post. user_id is kept for ownership/moderation only and is never displayed."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    alias = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(15), nullable=False, default="visible")  # visible | under_review | hidden
    report_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    comments = db.relationship('CommunityComment', backref='post', lazy=True,
                               cascade="all, delete-orphan", order_by="CommunityComment.created_at")
    reactions = db.relationship('CommunityReaction', backref='post', lazy=True, cascade="all, delete-orphan")

    def reaction_count(self, kind):
        return sum(1 for r in self.reactions if r.kind == kind)


class CommunityComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_post.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alias = db.Column(db.String(40), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(15), nullable=False, default="visible")
    report_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CommunityReaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_post.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # support | relate | heart
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', 'kind', name='uq_reaction'),)


class CommunityReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(10), nullable=False)  # post | comment
    target_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('target_type', 'target_id', 'user_id', name='uq_report'),)


class Psychiatrist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    specialty = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(40), nullable=False)       # e.g. Kathmandu, Lalitpur, Online
    languages = db.Column(db.String(80), nullable=False)
    bio = db.Column(db.String(300))
    work_days = db.Column(db.String(20), nullable=False)      # weekday numbers, Mon=0: "0,1,2,3,4"
    start_time = db.Column(db.String(5), nullable=False)      # "16:00"
    end_time = db.Column(db.String(5), nullable=False)        # "20:00" (last slot ends here)
    slot_minutes = db.Column(db.Integer, nullable=False, default=30)
    is_demo = db.Column(db.Boolean, nullable=False, default=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def days_label(self):
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        days = [int(d) for d in self.work_days.split(",")]
        return "Every day" if len(days) == 7 else ", ".join(names[d] for d in days)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    psychiatrist_id = db.Column(db.Integer, db.ForeignKey('psychiatrist.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)            # "12:30" local time
    status = db.Column(db.String(12), nullable=False, default="booked")       # booked | cancelled
    payment_method = db.Column(db.String(15), nullable=False)                 # khalti | khalti-demo | cash
    payment_status = db.Column(db.String(15), nullable=False, default="unpaid")  # unpaid | paid | cash_on_visit
    fee_npr = db.Column(db.Integer, nullable=False)
    khalti_pidx = db.Column(db.String(60))
    transaction_id = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    psychiatrist = db.relationship('Psychiatrist')
    # Database-level double-booking guard: one active booking per doctor per slot
    __table_args__ = (db.Index('uq_active_slot', 'psychiatrist_id', 'date', 'time', unique=True,
                               sqlite_where=db.text("status != 'cancelled'")),)

