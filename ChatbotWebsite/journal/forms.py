from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ChatbotWebsite.models import JOURNAL_MOODS


class JournalForm(FlaskForm):
    mood_tag = SelectField("How are you feeling?", validators=[DataRequired()],
                           choices=[(k, f"{v[0]} {k}") for k, v in JOURNAL_MOODS.items()])
    title = StringField("Title (optional)", validators=[Optional(), Length(max=100)])
    content = TextAreaField("What's on your mind?", validators=[DataRequired(), Length(max=10000)])
    submit = SubmitField("Save Journal")
