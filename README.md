# Lumora: MindCare Chatbot

A mental wellness chatbot for students that puts safety first. Every message is screened for crisis signals before anything else happens; high-risk messages go straight to SOS guidance instead of a normal reply. Everything else is routed through an intent classifier, a therapeutic response style the user chooses, and a fallback LLM for open-ended messages. It works in English, Nepali and Romanized Nepali, and comes with self-help tools: mood tracking, journaling, PHQ-9/GAD-7 self-tests, burnout checks, mindfulness exercises and an anonymous community.

Built as our final year project in Computer Engineering at Nepal Engineering College by Piya Neupane, Salina Kunwar and Suja Baral.

> Lumora is a self-help and awareness tool. It does not diagnose or treat any condition and is not a substitute for professional care.

## The Problem

Many students struggle with stress, anxiety, exam pressure and poor sleep but never reach out for help:

- **Stigma:** fear of being judged stops people from talking to anyone.
- **Access:** counselling is expensive, far away or has long waiting times.
- **Unsafe chatbots:** general-purpose bots can miss crisis signals or give confident, harmful advice.

Lumora gives students a private place to talk at any time, with crisis detection that always runs first and clear, non-diagnostic language throughout.

## Features

- **Risk-first safety screening:** crisis phrases in English, Nepali and Romanized Nepali (with spelling normalisation) trigger SOS guidance and an automatic redirect to the SOS page
- **Hybrid chat pipeline:** rule-based guards for greetings and short inputs, a Keras intent classifier (54 intents) with a confidence threshold, and a Mistral LLM fallback for low-confidence messages
- **Response styles:** Auto, Gentle Listener, Calm Coach, Reflective Therapist or Balanced, chosen per user
- **English / Nepali:** language detection, translation and Nepali replies for every intent
- **Guest and account modes:** guest chats are never stored; logged-in users get multi-session history ("Your Chats") and saved insights
- **Mood tracking and dashboard:** daily mood, VADER chat sentiment, trends, and PDF export
- **Self-tests:** PHQ-9, GAD-7 and a burnout check combining mood, journal and chat signals (results are indicative only)
- **Journaling and mindfulness:** private journal entries and guided breathing and grounding exercises
- **Anonymous community:** posts with tags and reactions, text screening, and auto-hide after repeated reports
- **Consultation booking:** psychiatrist slots with double-booking prevention, a calendar view and Khalti sandbox payment
- **Evaluation (J1, J2, J3):** sentiment model comparison against human labels, user feedback ratings, and usage vs outcome trends
- **Privacy controls:** delete messages, moods or journals by time window, delete conversations or the whole account, export your data as PDF

## How It Works

```
Message → session handling (guest / logged-in)
        → language detection (English, Nepali, Romanized Nepali) → translation
        → risk screening ── high risk ──→ SOS guidance + redirect
        → rule-based guards (greetings, too short, "idk")
        → intent classifier ── low confidence ──→ Mistral fallback
        → response style (listener / coach / therapist / balanced)
        → humanizer → reply
Side effects: sentiment score → mood dashboard, burnout signals, evaluation data
```

**Intent classifier comparison (54 intents):**

| Model                                   | Validation accuracy |
| --------------------------------------- | ------------------- |
| Naive Bayes (TF-IDF)                    | 87.61%              |
| Linear SVM (TF-IDF)                     | 90.07%              |
| Feed-forward NN (word + char TF-IDF)    | 94.70%              |
| LSTM (embeddings)                       | 88.73%              |


**Tech stack:** Python · Flask · SQLAlchemy · SQLite · TensorFlow/Keras · scikit-learn · NLTK · VADER · Mistral API · Bootstrap · Chart.js · FullCalendar · ReportLab · Khalti

## Quickstart

**Requirements:** Python 3.11

**1. Clone and install**

```
git clone https://github.com/PiyaNeu/REPO-NAME.git
cd REPO-NAME
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure**

Copy `.env.example` to `.env` and fill in your values. The Mistral, Khalti and SMTP keys are optional; the app runs without them.

**3. Train the intent model and load demo data**

```
python train.py
python seed.py
```

**4. Run**

```
flask run
```

Open **http://localhost:5000**.

> Before any real-world use, replace the placeholder SOS hotline numbers with verified ones.

## Screenshots

**Chat with SOS redirect**
![Chat]("C:\Users\ASUS TUF A15\OneDrive\Pictures\Screenshots\Screenshot 2026-10-02 145619.png")

**Mood dashboard**
![Mood dashboard](docs/screenshots/mood-dashboard.png)

**Self-tests and burnout check**
![Self-tests](docs/screenshots/self-tests.png)

**Anonymous community**
![Community](docs/screenshots/community.png)

**Consultation booking**
![Consultation](docs/screenshots/consultation.png)

**Evaluation (J1, J2, J3)**
![Evaluation](docs/screenshots/evaluation.png)
