"""English / Nepali interface toggle (report screenshots: "EN | ने").

Covers navigation and the main page headings/buttons. Missing keys fall back to
English, so untranslated pages still render. Chat replies follow the language the
user writes in (see chat/language.py), independent of this setting.
"""
from flask import session

LANGUAGES = {"en": "EN", "ne": "ने"}

STRINGS = {
    # Navigation
    "nav.chat": {"en": "Chat", "ne": "च्याट"},
    "nav.more": {"en": "More", "ne": "थप"},
    "nav.mood": {"en": "Mood", "ne": "मुड"},
    "nav.evaluation": {"en": "Evaluation", "ne": "मूल्याङ्कन"},
    "nav.journal": {"en": "Journal", "ne": "डायरी"},
    "nav.selftests": {"en": "Self-Tests", "ne": "आत्म-परीक्षण"},
    "nav.burnout": {"en": "Burnout Check", "ne": "बर्नआउट जाँच"},
    "nav.mindfulness": {"en": "Mindfulness", "ne": "माइन्डफुलनेस"},
    "nav.community": {"en": "Community", "ne": "समुदाय"},
    "nav.insights": {"en": "Saved Insights", "ne": "सुरक्षित सुझावहरू"},
    "nav.about": {"en": "About", "ne": "हाम्रो बारेमा"},
    "nav.mood_dashboard": {"en": "Mood Dashboard", "ne": "मुड ड्यासबोर्ड"},
    "nav.mood_checkin": {"en": "Mood Check-in", "ne": "आजको मुड"},
    "nav.mood_pdf": {"en": "Export Mood PDF", "ne": "मुड PDF डाउनलोड"},
    "nav.labeling": {"en": "Manual Labeling", "ne": "म्यानुअल लेबलिङ"},
    "nav.consultation": {"en": "Consultation", "ne": "परामर्श"},
    "nav.account": {"en": "Account", "ne": "खाता"},
    "nav.privacy": {"en": "Privacy & Data", "ne": "गोपनीयता र डाटा"},
    "nav.login": {"en": "Login", "ne": "लगइन"},
    "nav.register": {"en": "Register", "ne": "दर्ता"},
    "nav.logout": {"en": "Logout", "ne": "लगआउट"},
    "nav.guest": {"en": "Guest", "ne": "अतिथि"},
    # Home
    "home.title": {"en": "Lumora AI Chatbot", "ne": "लुमोरा एआई च्याटबट"},
    "home.subtitle": {"en": "Your friendly mental health companion. Chat anytime for guidance, tips, and exercises to support your emotional wellbeing.",
                      "ne": "तपाईंको मैत्रीपूर्ण मानसिक स्वास्थ्य साथी। भावनात्मक स्वास्थ्यका लागि मार्गदर्शन, सुझाव र अभ्यासहरूको लागि जुनसुकै बेला कुरा गर्नुहोस्।"},
    "home.chat_now": {"en": "CHAT NOW", "ne": "अहिले कुरा गर्नुहोस्"},
    "home.guest": {"en": "Continue as Guest", "ne": "अतिथिको रूपमा जारी राख्नुहोस्"},
    "home.about": {"en": "About Us", "ne": "हाम्रो बारेमा"},
    # Chat
    "chat.style": {"en": "Response style", "ne": "जवाफ दिने शैली"},
    "chat.sos": {"en": "SOS Help", "ne": "SOS सहायता"},
    "chat.help": {"en": "Need Help?", "ne": "सहायता चाहियो?"},
    "chat.disclaimer": {"en": "Lumora is a self-help tool, not a therapist or doctor.",
                        "ne": "लुमोरा आत्म-सहायता उपकरण हो, थेरापिस्ट वा डाक्टर होइन।"},
    "chat.placeholder": {"en": "Enter your message...", "ne": "आफ्नो सन्देश लेख्नुहोस्..."},
    "chat.send": {"en": "Send", "ne": "पठाउनुहोस्"},
    "chat.your_chats": {"en": "Your Chats", "ne": "तपाईंका च्याटहरू"},
    "chat.new": {"en": "New", "ne": "नयाँ"},
    "chat.search": {"en": "Search...", "ne": "खोज्नुहोस्..."},
    "chat.guest_note": {"en": "Guest mode — this conversation is not saved.",
                        "ne": "अतिथि मोड — यो कुराकानी सुरक्षित हुँदैन।"},
    "chat.saved_only": {"en": "Chats are saved only for logged-in users.",
                        "ne": "च्याटहरू लगइन गरेका प्रयोगकर्ताका लागि मात्र सुरक्षित हुन्छन्।"},
    "chat.welcome": {"en": "Please understand that this is a chatbot and not a real person. It is not a substitute for professional help.\n\nAlways best to seek professional help if you need to.\n\nHi there, welcome to LUMORA! Go ahead and send me a message. 💜",
                     "ne": "कृपया बुझ्नुहोस्, यो च्याटबट हो, वास्तविक मानिस होइन। यो पेशेवर सहायताको विकल्प होइन।\n\nआवश्यक परे पेशेवर सहायता लिनु नै उत्तम हुन्छ।\n\nनमस्ते, लुमोरामा स्वागत छ! मलाई सन्देश पठाउनुहोस्। 💜"},
    "chat.topics": {"en": "Topics", "ne": "विषयहरू"},
    "chat.tests": {"en": "Tests", "ne": "परीक्षण"},
    "chat.rate": {"en": "Rate this chat", "ne": "यो च्याटलाई मूल्याङ्कन गर्नुहोस्"},
    # SOS
    "sos.title": {"en": "SOS Hotlines in Nepal", "ne": "नेपालका SOS हेल्पलाइनहरू"},
    "sos.intro": {"en": "If you are in immediate danger or thinking about harming yourself, please contact emergency services or a helpline now. You don't have to go through this alone.",
                  "ne": "यदि तपाईं तत्काल खतरामा हुनुहुन्छ वा आफूलाई हानि गर्ने सोच्दै हुनुहुन्छ भने, कृपया अहिले नै आपतकालीन सेवा वा हेल्पलाइनमा सम्पर्क गर्नुहोस्। तपाईं एक्लै हुनुहुन्न।"},
    "sos.emergency": {"en": "Emergency services", "ne": "आपतकालीन सेवाहरू"},
    "sos.pending": {"en": "Contact number pending verification", "ne": "सम्पर्क नम्बर प्रमाणीकरण हुँदैछ"},
    "sos.show_map": {"en": "Show Map", "ne": "नक्सा हेर्नुहोस्"},
    # Mood
    "mood.question": {"en": "How are you feeling today?", "ne": "आज तपाईंलाई कस्तो महसुस भइरहेको छ?"},
    "mood.save": {"en": "Save", "ne": "सुरक्षित गर्नुहोस्"},
    "mood.export": {"en": "Export PDF", "ne": "PDF डाउनलोड"},
    # Common
    "common.not_diagnosis": {"en": "This is for reflection only and is not a diagnosis.",
                             "ne": "यो आत्म-चिन्तनका लागि मात्र हो, रोग निदान होइन।"},
}


def current_language():
    lang = session.get("ui_lang", "en")
    return lang if lang in LANGUAGES else "en"


def t(key):
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(current_language()) or entry["en"]
