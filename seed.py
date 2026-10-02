"""Seed the local database with demo data for presentations and screenshots.

Creates a verified demo account with ~3 weeks of mood check-ins, chats (run through
the real pipeline so sentiment/mood/crisis handling is genuine), journals, self-test
results, mindfulness use, session feedback, community posts and an appointment.

Usage:
    python seed.py                 # create/refresh the demo user (keeps other data)
    python seed.py --reset         # drop ALL tables first (local demo only!)
    python seed.py --admin you@example.com   # also make an existing user a Flask-Admin admin

Demo login (local demo only — change DEMO_PASSWORD in .env for anything shared):
    email:    demo@example.com
    password: value of DEMO_PASSWORD, default "Lumora@2026"
"""
import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from ChatbotWebsite import bcrypt, create_app, db  # noqa: E402
from ChatbotWebsite import models as m  # noqa: E402
from ChatbotWebsite.account.routes import delete_user_data  # noqa: E402
from ChatbotWebsite.community.moderation import random_alias  # noqa: E402
from ChatbotWebsite.consultation.booking import ensure_demo_psychiatrists  # noqa: E402
from ChatbotWebsite.sentiment import analyze, hybrid  # noqa: E402

NEPAL_OFFSET = timedelta(hours=5, minutes=45)

DEMO_EMAIL = "demo@example.com"
DEMO_USERNAME = "demo"
DAYS = 21

CHATS = [
    ["hi", "I'm stressed about my exams next week", "what should I do", "thank you"],
    ["I can't sleep at night, my mind keeps racing", "I tried putting my phone away", "ok I will try"],
    ["I feel lonely since I moved to the hostel", "I miss my family", "thanks for listening"],
    ["malai dherai tension bhayo", "pariksha ko dar lagcha", "dhanyabad"],
    ["I had a good day today, I passed my test!", "I feel proud of myself"],
    ["my boyfriend and I keep fighting", "I don't know if it's my fault"],
    ["I feel completely hopeless", "nothing helps"],
    ["can you guide me through a breathing exercise?", "that helped a bit"],
]
JOURNALS = [
    ("Calm", "Took a long walk after class. Felt calmer than yesterday."),
    ("Stressed", "So many assignments due. I wrote a plan for tomorrow and it helped a little."),
    ("Happy", "Had chai with friends and laughed a lot. Grateful for them."),
    ("Sad", "Missed home a lot today, felt low in the evening."),
    ("Anxious", "Presentation tomorrow. Practised twice. Still nervous."),
    ("Grateful", "Mom called. Small things matter."),
]
POSTS = [
    ("Exam week nerves", "Anyone else struggling to focus before finals? How do you manage?", "exams"),
    ("Can't sleep lately", "I keep waking up at 3am. What helps you get back to sleep?", "sleep"),
    ("Small win today", "I finally talked to my roommate about the noise. It went better than expected!", "relationship"),
]


def make_user(password):
    """Fresh demo user: any existing demo account and its data are removed first."""
    existing = m.User.query.filter_by(email=DEMO_EMAIL).first()
    if existing is not None:
        delete_user_data(existing)
        db.session.commit()
    user = m.User(username=DEMO_USERNAME, email=DEMO_EMAIL, is_verified=True, preferred_mode="auto",
                  password=bcrypt.generate_password_hash(password).decode())
    db.session.add(user)
    db.session.commit()
    return user


def seed_moods(user, rng):
    for i in range(DAYS, 0, -1):
        when = datetime.utcnow() - timedelta(days=i, hours=rng.randint(0, 6))
        mood = max(1, min(5, round(3.4 - 0.04 * i + rng.uniform(-1.1, 1.1))))
        db.session.add(m.MoodEntry(user_id=user.id, mood=mood, source="Manual", day=(when + NEPAL_OFFSET).date(),
                                   created_at=when, updated_at=when))


def seed_chats(app, user, rng):
    """Send messages through the real chat endpoint so sentiment, mood and safety are genuine."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    for i, convo in enumerate(CHATS):
        sid = None
        for text in convo:
            data = client.post("/chat/send", json={"message": text, "session_id": sid}).get_json()
            sid = data["session_id"]
        # Spread conversations over the past weeks
        when = datetime.utcnow() - timedelta(days=DAYS - i * 2 - 1, hours=rng.randint(1, 8))
        s = db.session.get(m.ChatSession, sid)
        s.created_at = s.updated_at = when
        for k, msg in enumerate(s.messages):
            msg.timestamp = when + timedelta(minutes=k)
        for entry in m.MoodEntry.query.filter(m.MoodEntry.message_id.in_([x.id for x in s.messages])):
            entry.created_at = entry.updated_at = when
            entry.day = (when + NEPAL_OFFSET).date()
        if rng.random() < 0.8:
            db.session.add(m.SessionFeedback(session_id=sid, user_id=user.id, session_title=s.title,
                                             rating=rng.choice([3, 4, 4, 5]), helpful=rng.random() < 0.75,
                                             created_at=when + timedelta(minutes=10)))
        db.session.commit()


def seed_rest(user, rng):
    for i, (tag, text) in enumerate(JOURNALS):
        when = datetime.utcnow() - timedelta(days=DAYS - i * 3)
        j = m.Journal(user_id=user.id, title=f"Feeling {tag}", content=text, mood_tag=tag,
                      mood=m.JOURNAL_MOODS[tag][1], date_created=when)
        j.sentiment_compound = analyze(text).compound
        h = hybrid(text)
        j.sentiment_score, j.sentiment_label = h.score, h.label
        db.session.add(j)
    for days_ago, phq, gad in ((20, 12, 10), (10, 9, 8), (2, 7, 6)):
        when = datetime.utcnow() - timedelta(days=days_ago)
        db.session.add(m.AssessmentResult(user_id=user.id, test="phq9", score=phq,
                                          band="Moderate" if phq >= 10 else "Mild", created_at=when))
        db.session.add(m.AssessmentResult(user_id=user.id, test="gad7", score=gad,
                                          band="Moderate" if gad >= 10 else "Mild", created_at=when))
    for _ in range(6):
        db.session.add(m.ToolUsage(user_id=user.id, tool="mindfulness",
                                   detail=rng.choice(["box-breathing", "body-scan", "grounding-54321"]),
                                   created_at=datetime.utcnow() - timedelta(days=rng.randint(1, DAYS))))
    for title, body, tag in POSTS:
        db.session.add(m.CommunityPost(user_id=user.id, alias=random_alias(rng), title=title, body=body, tag=tag,
                                       created_at=datetime.utcnow() - timedelta(days=rng.randint(1, 10))))
    ensure_demo_psychiatrists()
    doc = m.Psychiatrist.query.filter_by(name="Dr. Rohan KC").first()
    day = date.today() + timedelta(days=3)
    while str(day.weekday()) not in doc.work_days.split(","):
        day += timedelta(days=1)
    db.session.add(m.Appointment(user_id=user.id, psychiatrist_id=doc.id, date=day, time="12:30",
                                 payment_method="cash", payment_status="cash_on_visit", fee_npr=1500))
    db.session.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop and recreate ALL tables first")
    parser.add_argument("--admin", metavar="EMAIL", help="grant Flask-Admin access to this user")
    args = parser.parse_args()

    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False  # this process posts to its own endpoints; not a server setting
    with app.app_context():
        if args.reset:
            db.drop_all()
            db.create_all()
        rng = random.Random(7)
        user = make_user(os.environ.get("DEMO_PASSWORD", "Lumora@2026"))
        seed_moods(user, rng)
        db.session.commit()
        seed_chats(app, user, rng)
        seed_rest(user, rng)
        if args.admin:
            admin = m.User.query.filter_by(email=args.admin.strip().lower()).first()
            if admin is None:
                print(f"No user with email {args.admin}")
                return 1
            admin.is_admin = True
            db.session.commit()
            print(f"{admin.email} is now an admin (/admin)")
        counts = {name: getattr(m, name).query.filter_by(user_id=user.id).count()
                  for name in ("ChatSession", "ChatMessage", "MoodEntry", "Journal", "AssessmentResult",
                               "SessionFeedback", "CommunityPost", "Appointment")}
        print(f"Seeded demo account {DEMO_EMAIL}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
