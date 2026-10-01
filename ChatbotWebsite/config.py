import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # General Config
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key")
    
    # Database Config
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///" + os.path.join(basedir, "lumora.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Mail Config
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "False") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "yourgmail@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-app-password")

    # Security Salt for Tokens
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT", "your-salt-key")
