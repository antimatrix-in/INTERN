from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    employee_id = StringField('Employee ID or Registered Email', validators=[
        DataRequired(message='Please enter your Employee ID or registered email address.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password.')
    ])
    remember_me = BooleanField('Remember me on this device')
    submit = SubmitField('Sign In to Portal')


class AdminLoginForm(FlaskForm):
    email_or_id = StringField('Admin Email or Employee ID', validators=[
        DataRequired(message='Please enter your administrator email or ID.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password.')
    ])
    remember_me = BooleanField('Remember me on this device')
    submit = SubmitField('Sign In to Admin Portal')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Temporary Password', validators=[
        DataRequired(message='Please enter your current temporary password.')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='Please enter your new password.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password.')
    ])
    submit = SubmitField('Set New Password & Open Dashboard')
