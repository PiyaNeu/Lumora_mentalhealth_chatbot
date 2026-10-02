
# Lumora: MindCare Chatbot

A mental wellness chatbot for students that puts safety first. Every message is screened for crisis signals before anything else happens; high-risk messages go straight to SOS guidance instead of a normal reply. Everything else is routed through an intent classifier, a therapeutic response style the user chooses, and a fallback LLM for open-ended messages. It works in English, Nepali and Romanized Nepali, and comes with self-help tools: mood tracking, journaling, PHQ-9/GAD-7 self-tests, burnout checks, mindfulness exercises and an anonymous community.

Built as our final year project in Computer Engineering at Nepal Engineering College by Piya Neupane, Salina Kunwar and Suja Baral under the guidance of our supervisor Assistant Professor Anshu Ghimire.

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
git clone https://github.com/PiyaNeu/Lumora_mentalhealth_chatbot.git
cd Lumora_mentalhealth_chatbot
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
<img width="1905" height="915" alt="sos_redirect" src="https://github.com/user-attachments/assets/2ac094c6-34fc-42c6-a279-d17a508c7c9a" />

**Mood dashboard**
<img width="1500" height="817" alt="mood_dash" src="https://github.com/user-attachments/assets/fa89a0b9-1836-4884-86f1-aa34094c0a51" />

**Self-tests and burnout check**

<img width="1437" height="706" alt="self_test" src="https://github.com/user-attachments/assets/b9c3e710-4e96-4ac0-8726-528c4fdb9793" />

<img width="1075" height="830" alt="test" src="https://github.com/user-attachments/assets/723e0115-02b1-400d-88e2-fb94ffd88ede" />

<img width="1065" height="830" alt="another_test" src="https://github.com/user-attachments/assets/66c0e3e9-731c-4363-9927-057d32dc38cd" />

<img width="1077" height="785" alt="burnout_test" src="https://github.com/user-attachments/assets/be8fec09-03cf-440e-ac2b-ec38c4d6a0cf" />

<img width="1282" height="755" alt="burnout" src="https://github.com/user-attachments/assets/091b8350-8251-476c-b641-9ea0c3261713" />


**Anonymous community**
<img width="1245" height="635" alt="post_anon" src="https://github.com/user-attachments/assets/85a15873-5a7c-4a31-bd49-1815b7f6ac98" />


**Consultation booking**
<img width="1562" height="806" alt="consultation" src="https://github.com/user-attachments/assets/9681133e-5277-49bb-abda-b9a345a98d4f" />

**Evaluation (J1, J2, J3)**
<img width="1390" height="846" alt="j1" src="https://github.com/user-attachments/assets/3e0f1851-3e2a-4bd7-91ac-e86f3c3d7a2d" />

<img width="1397" height="837" alt="j2" src="https://github.com/user-attachments/assets/65b325bd-da5e-4a72-a3eb-501992fd6553" />

<img width="1356" height="800" alt="j3" src="https://github.com/user-attachments/assets/49193880-2680-4bc3-93d7-d00571004867" />

