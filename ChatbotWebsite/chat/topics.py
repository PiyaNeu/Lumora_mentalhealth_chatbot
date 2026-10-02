"""Human-readable topic names per intent, used when Lumora checks its guess with the user
("It sounds like this might be about exam stress — is that right?")."""

TOPIC_LABELS = {
    "stress_general": ("stress", "तनाव"),
    "anxiety_general": ("anxiety or worry", "चिन्ता"),
    "panic_attack": ("panic", "आत्तिने (प्यानिक)"),
    "sadness_low_mood": ("feeling low", "मन उदास हुनु"),
    "loneliness": ("loneliness", "एक्लोपन"),
    "anger_frustration": ("anger or frustration", "रिस वा झर्को"),
    "overwhelm": ("feeling overwhelmed", "धेरै कुराले थिचिएको महसुस"),
    "fear_worry_future": ("worry about the future", "भविष्यको चिन्ता"),
    "guilt_shame": ("guilt", "पछुतो"),
    "jealousy_comparison": ("comparing yourself to others", "अरूसँग तुलना"),
    "boredom_lack_interest": ("losing interest in things", "कुनै कुरामा रुचि नहुनु"),
    "tiredness_fatigue": ("tiredness", "थकान"),
    "crying_emotional": ("feeling very emotional", "धेरै भावुक हुनु"),
    "overthinking": ("overthinking", "धेरै सोच्नु"),
    "exam_stress": ("exam stress", "परीक्षाको तनाव"),
    "exam_failure_results": ("disappointing results", "नराम्रो नतिजा"),
    "study_focus": ("trouble focusing on studies", "पढाइमा ध्यान नजानु"),
    "procrastination": ("putting things off", "काम पछि सार्नु"),
    "time_management": ("managing your time", "समय व्यवस्थापन"),
    "academic_pressure_parents": ("pressure from family about studies", "पढाइबारे परिवारको दबाब"),
    "career_uncertainty": ("uncertainty about your future path", "करियरको अन्योल"),
    "burnout": ("burnout", "बर्नआउट"),
    "sleep_issues": ("sleep", "निद्रा"),
    "nightmares": ("bad dreams", "नराम्रो सपना"),
    "appetite_eating_changes": ("changes in eating", "खानपानमा परिवर्तन"),
    "physical_symptoms_stress": ("stress showing up in your body", "शरीरमा देखिने तनाव"),
    "relationship_problems": ("your relationship", "तपाईंको सम्बन्ध"),
    "breakup_heartbreak": ("heartbreak", "माया टुट्नु"),
    "family_conflict": ("tension with family", "परिवारसँगको तनाव"),
    "friendship_issues": ("a friendship", "साथीसँगको सम्बन्ध"),
    "social_anxiety_shyness": ("nervousness around people", "मानिससँग बोल्दा डर"),
    "bullying_harassment": ("being treated badly by others", "अरूले नराम्रो व्यवहार गर्नु"),
    "homesickness": ("missing home", "घरको याद"),
    "low_self_esteem": ("how you see yourself", "आफूप्रतिको धारणा"),
    "motivation_goals": ("motivation", "जाँगर"),
    "self_care": ("taking care of yourself", "आफ्नो हेरचाह"),
    "body_image": ("how you feel about your body", "आफ्नो शरीरबारेको भावना"),
    "grief_loss": ("losing someone", "प्रियजन गुमाउनु"),
    "breathing_exercise": ("calming your breathing", "सास शान्त पार्नु"),
    "mindfulness_grounding": ("grounding yourself", "मन वर्तमानमा ल्याउनु"),
    "coping_skills": ("ways to cope", "सामना गर्ने उपाय"),
    "journaling_prompt": ("writing down your thoughts", "भावना लेख्नु"),
    "professional_help": ("getting professional support", "पेशेवर सहयोग"),
    "substance_use": ("drinking or using substances", "रक्सी वा लागूपदार्थ"),
}


def check_line(tag, lang):
    """The 'is that right?' sentence for a tentative guess, or None if the intent has no label."""
    label = TOPIC_LABELS.get(tag)
    if label is None:
        return None
    if lang == "ne":
        return f"मलाई ठ्याक्कै पक्का भएन, तर यो {label[1]}बारे हो जस्तो लाग्यो — हो भने यो उपयोगी हुन सक्छ:"
    return f"I'm not completely sure, but it sounds like this might be about {label[0]}. If so, this might help:"


def confirm_question(lang):
    if lang == "ne":
        return "मैले ठिक बुझेँ? नभए, अलि बढी भन्नुहोस् न।"
    return "Did I get that right? If not, tell me a bit more and I'll try again."
