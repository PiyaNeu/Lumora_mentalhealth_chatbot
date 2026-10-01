import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(basedir)

# Settings come from .env at the project root (see .env.example). The legacy
# ChatbotWebsite/.env is still read as a fallback; it never overrides the root file.
load_dotenv(os.path.join(project_root, ".env"))
load_dotenv(os.path.join(basedir, ".env"))


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # General
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DEBUG = _bool("FLASK_DEBUG", False)
    # Base URL used in emails (verification links). Set to your ngrok/Render domain.
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # Database: a relative sqlite path resolves inside Flask's instance/ folder
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///lumora.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail (SMTP)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", os.environ.get("MAIL_USERNAME"))
    MAIL_SUPPRESS_SEND = _bool("MAIL_SUPPRESS_SEND", False)

    # Token salt for email verification / password reset
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", "dev-only-salt")

    # Chatbot
    MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(project_root, "model"))
    INTENT_CONFIDENCE_THRESHOLD = float(os.environ.get("INTENT_CONFIDENCE_THRESHOLD", 0.55))
    LOAD_INTENT_MODEL = _bool("LOAD_INTENT_MODEL", True)
    MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")  # optional; fallback is skipped without it
    MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
    MISTRAL_TIMEOUT = float(os.environ.get("MISTRAL_TIMEOUT", 15))

    # Community moderation
    COMMUNITY_REPORT_THRESHOLD = int(os.environ.get("COMMUNITY_REPORT_THRESHOLD", 3))

    # Consultation / Khalti (sandbox)
    CONSULTATION_FEE_NPR = int(os.environ.get("CONSULTATION_FEE_NPR", 1500))
    KHALTI_SECRET_KEY = os.environ.get("KHALTI_SECRET_KEY")
    KHALTI_BASE_URL = os.environ.get("KHALTI_BASE_URL", "https://dev.khalti.com/api/v2").rstrip("/")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    LOAD_INTENT_MODEL = False
    MISTRAL_API_KEY = None
    KHALTI_SECRET_KEY = None
    PUBLIC_BASE_URL = "http://localhost"
