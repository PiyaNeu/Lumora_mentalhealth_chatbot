from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from ChatbotWebsite.chat.brain import MODE_LABELS
from ChatbotWebsite.models import User


class AccountForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=20)])
    preferred_mode = SelectField("Preferred mode", choices=list(MODE_LABELS.items()))
    picture = FileField("Update Profile Picture", validators=[FileAllowed(["jpg", "jpeg", "png"], "Images only (jpg, png).")])
    submit = SubmitField("Update")

    def validate_username(self, username):
        if username.data != current_user.username and User.query.filter_by(username=username.data).first():
            raise ValidationError("That username is taken. Please choose another.")
