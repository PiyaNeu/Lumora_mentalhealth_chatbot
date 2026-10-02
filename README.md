# LUMORA: MindCare Chatbot

A non-diagnostic mental-wellbeing chatbot and self-help web app for students in Nepal
(final-year project, Nepal Engineering College). Lumora listens, offers low-risk coping
ideas, and puts **safety first**: messages showing crisis risk are routed to SOS guidance
before anything else happens.

> Lumora is an educational self-help tool. It does **not** diagnose or treat any condition
> and is not an emergency service.

## Features

| Area | What it does | Code |
|---|---|---|
| Chat pipeline | Session handling → language detection (Devanagari + Roman Nepali) → basic translation → **risk-first safety screen** (high = SOS, medium = cautious reply) → rule guards → Keras intent model with confidence threshold → Mistral fallback (optional) → "brain" response style → humanizer | `ChatbotWebsite/chat/` |
| Your Chats | Guest chats are never stored; logged-in users get sessions with switch / search / delete / new, plus **Save insight** | `chat/routes.py`, `static/js/chat.js` |
| Response modes | Auto, Gentle Listener, Calm Coach, Reflective Therapist, Balanced | `chat/brain.py` |
| Sentiment | VADER, a Keras ML classifier and a Hybrid (ML + rules), stored per message and journal | `sentiment.py` |
| Mood tracker | 1–5 daily check-in (one per day, updates in place) + chat-derived moods; daily/weekly/monthly charts, streak, trend insight, chat sentiment trend, mood vs sentiment, PDF report | `mood/` |
| Journal | Create / view / edit / delete, mood tag, pagination, prompts | `journal/` |
| Self-tests | PHQ-9, GAD-7 (standard items and bands), burnout questionnaire and a signals-based burnout check. Results are indicative only | `selfhelp/` |
| Mindfulness | Guided exercises, audio players or placeholders, box-breathing pacer | `data/mindfulness.json` |
| Community | Anonymous posts/comments, allowed tags, Support/Relate/Heart, report + auto-hide, text screening, Recent / Support-first | `community/` |
| SOS | Guest-accessible Nepal helpline page | `sos_config.py` |
| Consultation | Psychiatrist list, slot booking with double-booking prevention, calendar (paid / cash on visit / unpaid), Khalti sandbox | `consultation/` |
| Evaluation | Manual labeling, J1 (Macro-F1 + confusion matrix), J2 (session feedback), J3 (usage & outcomes) — all from the real database | `evaluation/` |
| Privacy | Delete messages/moods/journals by time window, delete one or all conversations, export my data (PDF), delete account | `account/` |
| UI | Bootstrap, lavender theme, English / नेपाली toggle, responsive | `templates/`, `i18n.py` |

## Architecture

```
Browser (Bootstrap + vanilla JS, Chart.js, FullCalendar)
   │  HTTPS, CSRF-protected forms / fetch
   ▼
Flask app (create_app) ── blueprints: main · auth · chat · mood · journal · community
   │                                  selfhelp · consultation · evaluation · account
   │
   ├── Chat pipeline (chat/pipeline.py)
   │     language.py → translate.py → safety.py ─┬─ high risk → SOS reply (stop)
   │                                             ├─ medium   → cautious reply (stop)
   │                                             └─ guards.py → intent.py (Keras FFNN)
   │                                                   │ confident → response bank
   │                                                   └ low       → llm.py (Mistral, optional)
   │                                             → brain.py (style) → humanizer.py
   ├── ML: ml/preprocess.py, ml/features.py (word + char TF-IDF + history), model/*.keras
   ├── Sentiment: VADER + Keras classifier + rules (sentiment.py)
   ├── Reports: ReportLab + matplotlib PDFs (mood/pdf.py, account/export.py)
   └── SQLite via SQLAlchemy (instance/lumora.db) · Flask-Login · Flask-WTF · Flask-Mail
External (optional): SMTP (email verification), Mistral API, Khalti ePayment sandbox
```

## Setup

Requires Python 3.11 (TensorFlow 2.20).

```bash
python -m venv env
```

```bash
env\Scripts\activate
```

(On macOS/Linux: `source env/bin/activate`.)

```bash
pip install -r requirements.txt
```

```bash
copy .env.example .env
```

Edit `.env`: set `SECRET_KEY` and `SECURITY_PASSWORD_SALT`. Then fill the optional parts you want:

- **Email verification:** SMTP settings. For Gmail, use an App Password.
- **Mistral fallback:** `MISTRAL_API_KEY`. The app works without it.
- **Khalti sandbox:** `KHALTI_SECRET_KEY` (test key). Without it, a clearly-labelled demo checkout is used.
- **Public links:** `PUBLIC_BASE_URL`, your ngrok or Render URL, so emailed links work from other devices.

Start the app:

```bash
python run.py
```

Open http://127.0.0.1:5000. Without SMTP settings, verification emails are written to the log instead of being sent.

### Demo data

```bash
python seed.py
```

This creates `demo@example.com` (password `Lumora@2026`, or `DEMO_PASSWORD` from `.env`) with three weeks of moods, chats, journals, self-test results, feedback, community posts and an appointment. Re-running the script replaces the demo account. To give a user access to `/admin`, add `--admin you@example.com`.

## Training the models

The trained models are committed in `model/`, so the app runs right after cloning. To rebuild them:

```bash
python build_dataset.py
```

Regenerates `ChatbotWebsite/data/intents_augmented.json` from the hand-written `intents_seed.json` and mapped mid-term patterns.

```bash
python train.py
```

Intent model: word + char TF-IDF + history features → Keras FFNN, Adam, EarlyStopping, ReduceLROnPlateau, stratified 80/20. Writes `model/` and `reports/` (accuracy curve, loss curve, per-intent precision/recall/F1, confidence table). Add `--split grouped` for the stricter unseen-sentence evaluation.

```bash
python compare_models.py
```

Naive Bayes vs Linear SVM vs FFNN vs LSTM on both splits → `reports/model_comparison.*`.

```bash
python train_sentiment.py
```

ML sentiment classifier used by J1 and the hybrid sentiment.

### Results (real, from `reports/`)

Dataset: 54 intents, 6,696 samples (775 hand-written, 285 reused from the mid-term data, 5,292 augmented variants, 344 history follow-ups). The original final-project dataset was lost; this one was rebuilt.

| Model | Validation accuracy, stratified 80/20 (report method) | Unseen-sentence split |
|---|---|---|
| Naive Bayes (TF-IDF) | 88.88% | 31.84% |
| Linear SVM (TF-IDF) | 91.19% | 40.94% |
| **Feed-Forward NN (Keras, production)** | **96.04%** (macro-F1 0.961) | 43.10% |
| LSTM (tokenizer + embedding) | 90.00% | 31.62% |

- **Stratified 80/20** is the method described in the report. Augmented variants of a sentence can appear in both training and validation, so it measures recognition of known phrasings.
- **Unseen-sentence split** keeps every variant of a sentence on one side. It's a stricter estimate for brand-new messages and shows that more varied training sentences are the main room for improvement.
- **Confidence threshold:** at the app's 0.55 threshold, 93.6% of validation messages are answered by the model, with 99.8% accuracy. Messages below the threshold go to the Mistral fallback or a supportive fallback reply.
- **History features:** follow-up messages are classified correctly 40.6% of the time with history, against 1.6% without it.
- **J1 / J2 / J3:** these are computed live from your database (Evaluation menu). J1 needs at least 10 messages labelled on the Manual Labeling page.

## Tests

```bash
python -m pytest
```

438 tests. They mirror the report's Chapter 4 test-case tables:

| Report table | Test file |
|---|---|
| 4.4.1 Authentication (TC-A1…A5) | `tests/test_auth.py` |
| 4.4.2 / 4.4.5 Sentiment (TC-B, TC-E) | `tests/test_sentiment.py` |
| 4.4.3 Chat sessions (TC-C1…C3) | `tests/test_chat_sessions.py` |
| 4.4.4 Chatbot interaction (TC-D1…D4) | `tests/test_chatbot_input.py` |
| Crisis / safety screening (§4.2.4) | `tests/test_crisis_detection.py` |
| 4.4.6 Mood tracker (TC-F1…F3), 4.4.7 PDF (TC-G1, G2) | `tests/test_mood.py` |
| 4.4.8 Journal (TC-H1…H3) | `tests/test_journal.py` |
| 4.4.9 Self-tests (TC-I1, I2) | `tests/test_selftests.py` |
| 4.4.10 SOS (TC-K1, K2) | `tests/test_sos.py` |
| 4.4.11 Booking & calendar (TC-L1…L4), 4.4.12 Payment (TC-M1…M3) | `tests/test_consultation.py` |
| Community, evaluation, privacy, UI, intent model | `test_community.py`, `test_evaluation.py`, `test_privacy.py`, `test_ui.py`, `test_intent_model.py` |

TC-N1/N2 (ngrok public access) need a manual check: run `ngrok http 5000`, set `PUBLIC_BASE_URL` to the ngrok URL, open it on another device and register to confirm the verification email link uses the ngrok domain.

## Before real use (TODO)

- **SOS numbers:** every helpline number in `ChatbotWebsite/sos_config.py` is a placeholder. Verify each with the organisation, fill it in and set `verified=True`. Unverified numbers are never displayed.
- **Psychiatrists:** the three profiles are demo data. Replace them with real, consenting practitioners before real bookings.
- **Mindfulness audio:** four exercises have no audio yet. Add MP3s to `static/mindfulness/` and set `audio` in `data/mindfulness.json`. Also confirm the licence of the existing four MP3s, which came with the mid-term code.
- **Deployment:** use a production server (e.g. gunicorn on Render) and consider PostgreSQL for more users.

## Screenshots

Add screenshots to `docs/screenshots/` with these names:

`chat.png` · `sos.png` · `journals.png` · `community.png` · `saved-insights.png` · `modes.png` ·
`manual-labeling.png` · `j1.png` · `j2.png` · `j3.png` · `mood-dashboard.png` · `mood-report.png` ·
`privacy.png` · `burnout.png` · `consultation.png` · `checkout.png` · `calendar.png`

## Project structure

```
ChatbotWebsite/
  __init__.py        app factory, extensions, blueprints, Flask-Admin
  config.py          settings from .env
  models.py          SQLAlchemy models
  chat/              pipeline, safety, guards, intent, llm, brain, humanizer, routes
  ml/                preprocessing, features, training helpers
  mood/ journal/ selfhelp/ community/ consultation/ evaluation/ account/ auth/ main/
  data/              intents_seed.json, intents_augmented.json, sentiment_extra.json, mindfulness.json
  templates/ static/
model/               trained intent + sentiment models
reports/             training curves, metrics, model comparison
tests/               pytest suite
build_dataset.py  train.py  compare_models.py  train_sentiment.py  seed.py  run.py
```

## Team

Piya Neupane · Salina Kunwar · Suja Baral — supervised by Asst. Prof. Anshu Ghimire,
Department of Computer Science and Engineering, Nepal Engineering College.
