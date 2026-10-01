import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from ChatbotWebsite.models import User

PASSWORD_RULE = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#^_\-]).{8,}$")


def strong_password(form, field):
    if not PASSWORD_RULE.match(field.data or ""):
        raise ValidationError(
            "Password needs 8+ characters, an uppercase letter, a number and a special character."
        )


class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")]
    )
    submit = SubmitField("Sign Up")

    def validate_username(self, username):
        if User.query.filter_by(username=username.data.strip()).first():
            raise ValidationError("That username is taken. Please choose another.")

    def validate_email(self, email):
        if User.query.filter_by(email=email.data.strip().lower()).first():
            raise ValidationError("Email already exists")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Log In")


class RequestResetForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")]
    )
    submit = SubmitField("Reset Password")
