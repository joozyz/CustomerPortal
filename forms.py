from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo
from models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required")
    ])
    remember_me = BooleanField('Remember Me')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if not user:
            raise ValidationError('Email not registered')

class RequestPasswordResetForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if not user:
            raise ValidationError('Email address not found')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

class SMTPSettingsForm(FlaskForm):
    smtp_server = StringField('SMTP Server', validators=[
        DataRequired(message="SMTP server is required")
    ])
    smtp_port = StringField('SMTP Port', validators=[
        DataRequired(message="SMTP port is required")
    ])
    smtp_username = StringField('SMTP Username', validators=[
        DataRequired(message="SMTP username is required"),
        Email(message="Please enter a valid email address")
    ])
    smtp_password = PasswordField('SMTP Password', validators=[
        DataRequired(message="SMTP password is required")
    ])
    submit = SubmitField('Save Settings')