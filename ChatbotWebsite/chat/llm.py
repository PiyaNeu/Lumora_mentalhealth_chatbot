"""Mistral generative fallback (report §3.7.4, §3.7.7c).

Used only when intent confidence is low or the message is open-ended. Optional:
with no MISTRAL_API_KEY (or on any API error) it returns None and the pipeline
uses its built-in supportive fallback instead.
"""
import requests
from flask import current_app

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = """You are Lumora, a supportive mental-wellbeing companion for students in Nepal.
You are NOT a therapist, counsellor or doctor, and you must say so if asked.

Rules you must always follow:
- Never diagnose, never say the user "has" a condition or disorder, and never name a diagnosis for them.
- Never recommend, name or discuss medication or doses. No medical or legal advice.
- If the user mentions self-harm, suicide, abuse or being in danger, tell them to open the SOS page
  for Nepal helplines and contact local emergency services right away. Do not attempt therapy in that case.
- Suggest only low-risk self-help ideas: slow breathing, grounding, short walks, rest, sleep routine,
  journaling, breaking tasks into small steps, talking to someone they trust.
- Encourage seeing a professional if distress is severe or lasts for weeks.
- Keep the reply under 120 words, warm, plain and non-judgemental. Ask at most one gentle question.
- Do not invent phone numbers, names of services or statistics.

Response style for this reply: {style}
Reply language: {language}"""

STYLE_HINTS = {
    "listener": "Gentle Listener — validate and reflect feelings, minimal advice, one open question.",
    "coach": "Calm Coach — brief validation, then 2-3 concrete, numbered small steps.",
    "therapist": "Reflective Therapist — reflect the underlying feeling and offer one gentle reframing question "
                 "(CBT-informed, non-clinical).",
    "balanced": "Balanced — short validation, one practical tip, one gentle question.",
}

LANGUAGE_HINTS = {
    "en": "English",
    "ne": "simple Nepali in Devanagari script",
    "ne-rom": "simple Nepali in Devanagari script",
}


def is_available():
    return bool(current_app.config.get("MISTRAL_API_KEY"))


def _chat(messages, max_tokens=300, temperature=0.6):
    cfg = current_app.config
    try:
        resp = requests.post(
            MISTRAL_URL,
            headers={"Authorization": f"Bearer {cfg['MISTRAL_API_KEY']}"},
            json={"model": cfg["MISTRAL_MODEL"], "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=cfg.get("MISTRAL_TIMEOUT", 15),
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return content.strip() or None
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        current_app.logger.warning("Mistral call failed: %s", exc)
        return None


def generate_reply(message, strategy, lang="en", history=None):
    """Generate a constrained supportive reply, or None if unavailable."""
    if not is_available():
        return None
    system = SYSTEM_PROMPT.format(style=STYLE_HINTS.get(strategy, STYLE_HINTS["balanced"]),
                                  language=LANGUAGE_HINTS.get(lang, "English"))
    messages = [{"role": "system", "content": system}]
    for turn in (history or [])[-6:]:
        messages.append({"role": "user" if turn["role"] == "user" else "assistant", "content": turn["text"]})
    messages.append({"role": "user", "content": message})
    return _chat(messages)


def translate_to_nepali(text):
    """Translate a reply into Nepali (Devanagari). Returns None if unavailable."""
    if not is_available():
        return None
    return _chat([
        {"role": "system", "content": "Translate the user's text into simple, natural Nepali (Devanagari). "
                                      "Keep the meaning and tone. Output only the translation."},
        {"role": "user", "content": text},
    ], max_tokens=500, temperature=0.2)
