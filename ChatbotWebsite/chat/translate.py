"""Basic Nepali → English translation for the NLP pipeline (report §3.7.2).

Dictionary-based: known phrases first, then word by word. Unknown words are kept as
they are (users often mix English into Nepali). As the report says, this is an
auxiliary step and is not accurate translation — it only needs to give the safety
screen and intent model enough English keywords to work with.
"""
import re

# Phrases are matched before single words. Keys are lowercase.
PHRASES = {
    # Romanized
    "marna man lagyo": "i want to die",
    "marna mann lagyo": "i want to die",
    "marna man lagcha": "i want to die",
    "marna man cha": "i want to die",
    "jiuna man chaina": "i do not want to live",
    "jiuna mann chaina": "i do not want to live",
    "aafu lai chot": "hurt myself",
    "nindra lagdaina": "i cannot sleep",
    "nindra aaudaina": "i cannot sleep",
    "nindra paryo": "i am sleepy",
    "k garne thaha chaina": "i don't know what to do",
    "ke garne thaha chaina": "i don't know what to do",
    "thaha chaina": "i don't know",
    "raksi dherai khana thale": "i started drinking a lot of alcohol",
    "raksi khana thale": "i started drinking alcohol",
    "raksi khanchu": "i drink alcohol",
    "malai hepchan": "they bully me i am being bullied",
    "kura garna man lagyo": "i want to talk to someone",
    "doctor sanga": "with a doctor",
    "stress bhayo": "i am stressed",
    "stress cha": "i am stressed",
    "pressure cha": "i feel a lot of pressure and stress",
    "exam cha": "i have an exam",
    "pariksha cha": "i have an exam",
    "ramro aayena": "was bad",
    "breakup bhayo": "we broke up",
    "koi sathi chaina": "i have no friends",
    "kohi sathi chaina": "i have no friends",
    "kohi chaina": "i have no one",
    "koi chaina": "i have no one",
    "arulai dekhera": "comparing myself to others",
    "saas ferna garo": "i can't breathe properly",
    "man ramro chaina": "i feel sad",
    "man ramro lagena": "i feel sad",
    "ramro lagena": "i feel bad",
    "man dukhyo": "i feel hurt",
    "dukha lagyo": "i feel sad",
    "kehi garna man lagdaina": "i don't feel like doing anything",
    "padhna man lagdaina": "i can't focus on studying",
    "nindra lagena": "i could not sleep",
    "ghar ko yaad aayo": "i miss home",
    "aama ko yaad aayo": "i miss my mother",
    "sathi le dhoka diyo": "my friend betrayed me",
    "ris uthyo": "i am angry",
    "pariksha aauna lagyo": "exams are coming",
    "fail bhaye": "i failed",
    "result naramro aayo": "my result was bad",
    "eklo chu": "i am lonely",
    "eklo mahasus huncha": "i feel lonely",
    "thakai lagyo": "i am tired",
    "kam ko chaina": "i am useless",
    "kaam ko chaina": "i am useless",
    "jindagi sakiyo": "my life is over",
    "jindagi bekar": "life is useless",
    "tension bhayo": "i am stressed",
    "tension cha": "i am stressed",
    "dar lagyo": "i am scared",
    "dar lagcha": "i am scared",
    "eklo mahasus": "i feel lonely",
    "eklo feel": "i feel lonely",
    "man dukheko": "i feel hurt",
    "ramro chaina": "not good",
    "ramro chha": "good",
    "k cha": "how are you",
    "k chha": "how are you",
    "kasto cha": "how are you",
    "pariksha aaudai": "exam is coming",
    # Devanagari
    "मर्न मन लाग्यो": "i want to die",
    "मर्न मन छ": "i want to die",
    "जिउन मन छैन": "i do not want to live",
    "बाँच्न मन छैन": "i do not want to live",
    "निद्रा लाग्दैन": "i cannot sleep",
    "निद्रा आउँदैन": "i cannot sleep",
    "के गर्ने थाहा छैन": "i don't know what to do",
    "थाहा छैन": "i don't know",
    "डर लाग्यो": "i am scared",
    "डर लाग्छ": "i am scared",
    "एक्लो महसुस": "i feel lonely",
    "मन दुखेको": "i feel hurt",
    "राम्रो छैन": "not good",
    "के छ": "how are you",
    "कस्तो छ": "how are you",
}

WORDS = {
    # Romanized
    "ma": "i", "malai": "i", "mero": "my", "meri": "my", "timi": "you", "tapai": "you",
    "dukha": "sad", "dukhi": "sad", "udas": "sad", "tension": "stress", "pir": "worry",
    "chinta": "anxiety", "dar": "scared", "darr": "scared", "ris": "angry", "khusi": "happy",
    "ramro": "good", "naramro": "bad", "thakeko": "tired", "thakai": "tired", "eklo": "lonely",
    "nindra": "sleep", "sutna": "sleep", "pariksha": "exam", "padhai": "study", "sathi": "friend",
    "ghar": "home", "parivar": "family", "aama": "mother", "buwa": "father", "maya": "love",
    "prem": "love", "kaam": "work", "man": "feel", "mann": "feel", "chaina": "not", "chhaina": "not",
    "xaina": "not", "sakdina": "cannot", "marna": "die", "aatmahatya": "suicide",
    "atmahatya": "suicide", "jiuna": "live", "maddat": "help", "sahayog": "help",
    "namaste": "hello", "dhanyabad": "thanks", "dhanyawad": "thanks", "dherai": "very",
    "ekdam": "very", "ali": "a bit", "aaja": "today", "hijo": "yesterday", "bholi": "tomorrow",
    "bihe": "marriage", "garnu": "do", "garna": "do", "lagyo": "feel", "lagcha": "feel",
    "lagchha": "feel", "cha": "is", "chha": "is", "xa": "is", "chhu": "am", "xu": "am",
    "bhayo": "happened", "yaad": "miss", "aayo": "came", "dhoka": "betrayed", "jindagi": "life",
    "jiban": "life", "sakiyo": "over", "bekar": "useless", "sathiharu": "friends", "padhna": "study",
    "thakai": "tired", "dukhyo": "hurt", "dukheko": "hurt", "lagena": "not", "pardaina": "do not like",
    "garchu": "do", "huncha": "happens", "aafno": "my own", "afno": "my own", "chu": "am",
    "ko": "", "le": "", "lai": "", "nai": "", "pani": "also", "aba": "now",
    "chhodi": "left me", "chodi": "left me", "chhodyo": "left me", "chodyo": "left me",
    "jhagada": "fight", "sanga": "with", "sadhai": "always", "kura": "talk",
    "tauko": "head", "dukhcha": "hurts", "sapana": "dream", "dekhchu": "see", "khana": "eat", "runa": "cry",
    "raksi": "alcohol", "hepchan": "bully me", "saas": "breath", "ferne": "breathing", "abhyas": "exercise",
    "sikaunus": "teach me", "dhyan": "meditation", "kasari": "how", "garne": "do", "mutu": "heart",
    "dhadkiyo": "racing", "garo": "hard", "bhabishya": "future", "sochchu": "overthink", "sabai": "everything",
    "pachi": "later", "sarchu": "postpone", "aayena": "did not come", "koi": "no one", "kohi": "no one",
    "lagiraako": "feel", "lagirakheko": "feel", "uthcha": "rises", "uthyo": "rose", "arulai": "others",
    "dekhera": "seeing", "stress": "stressed", "pressure": "pressure", "hajurama": "grandmother",
    "bitnubhayo": "passed away", "biteko": "passed away", "thale": "started",
    "birami": "sick", "bimar": "sick", "jwaro": "fever", "jaro": "fever", "aspatal": "hospital",
    "बिरामी": "sick", "ज्वरो": "fever", "अस्पताल": "hospital",
    # Devanagari
    "म": "i", "मलाई": "i", "मेरो": "my", "तिमी": "you", "दुःख": "sad", "दुखी": "sad",
    "उदास": "sad", "टेन्सन": "stress", "तनाव": "stress", "पीर": "worry", "चिन्ता": "anxiety",
    "डर": "scared", "रिस": "angry", "खुसी": "happy", "राम्रो": "good", "नराम्रो": "bad",
    "थाकेको": "tired", "थकाइ": "tired", "एक्लो": "lonely", "निद्रा": "sleep", "परीक्षा": "exam",
    "पढाइ": "study", "साथी": "friend", "घर": "home", "परिवार": "family", "आमा": "mother",
    "बुबा": "father", "माया": "love", "काम": "work", "मन": "feel", "छैन": "not", "सक्दिन": "cannot",
    "मर्न": "die", "आत्महत्या": "suicide", "मद्दत": "help", "सहयोग": "help", "नमस्ते": "hello",
    "धन्यवाद": "thanks", "धेरै": "very", "एकदम": "very", "अलि": "a bit", "आज": "today",
    "छ": "is", "छु": "am", "भयो": "happened", "लाग्यो": "feel", "लाग्छ": "feel",
}

_TOKEN = re.compile(r"[ऀ-ॿ]+|[a-zA-Z']+|[^\s]")

# Common Romanized spelling variants → one form, so phrases/words above match
VARIANTS = {
    "chhaina": "chaina", "xaina": "chaina", "chha": "cha", "xa": "cha", "chhu": "chu", "xu": "chu",
    "mann": "man", "lagxa": "lagcha", "lagchha": "lagcha", "hunxa": "huncha", "hunchha": "huncha",
    "yad": "yaad", "ayo": "aayo", "malie": "malai", "malae": "malai", "kei": "kehi", "garxu": "garchu",
    "dukkha": "dukha", "sathii": "sathi", "jindegi": "jindagi", "zindagi": "jindagi", "jeevan": "jiban",
    "jiwan": "jiban", "jivan": "jiban", "pariksa": "pariksha", "ghara": "ghar",
}


def to_english(text, lang):
    """Translate Nepali (Devanagari or Romanized) text to rough English. English passes through."""
    if lang == "en" or not text:
        return text
    # Pad punctuation (incl. the Devanagari danda) so phrases match at word boundaries
    out = re.sub(r"([।॥]|[^\w\s'ऀ-ॿ])", r" \1 ", text.lower())
    out = " " + " ".join(VARIANTS.get(w, w) for w in out.split()) + " "
    for phrase in sorted(PHRASES, key=len, reverse=True):
        out = out.replace(f" {phrase} ", f" {PHRASES[phrase]} ")
    tokens = _TOKEN.findall(out)
    words = []
    for i, tok in enumerate(tokens):
        if tok == "ma":
            # "ma" = "I" at the start of a sentence, but "in" after a noun ("exam ma", "ghar ma")
            words.append("i" if i == 0 or tokens[i - 1] in (".", ",", "!", "?", "।") else "in")
        else:
            words.append(_word(tok))
    return re.sub(r"\s+", " ", " ".join(words)).strip()


# Postpositions often written attached to the noun: साथीले, घरमा, sathile, gharma
_SUFFIXES = ("ले", "लाई", "को", "मा", "le", "lai", "ko", "ma")


def _word(tok):
    if tok in WORDS:
        return WORDS[tok]
    for suf in _SUFFIXES:
        stem = tok[: -len(suf)]
        if tok.endswith(suf) and len(stem) >= 2 and stem in WORDS:
            return WORDS[stem]
    return tok
