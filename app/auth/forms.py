from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(message='Please enter your email address.'),
        Email(message='Please enter a valid email address.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password.')
    ])
    remember_me = BooleanField('Remember me on this device')
    submit = SubmitField('Sign In to Portal')


class RegistrationForm(FlaskForm):
    # Step 1: Personal Information
    full_name = StringField('Full Name', validators=[
        DataRequired(message='Please enter your full name as per academic records.'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters.')
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message='Please enter your email address.'),
        Email(message='Please enter a valid email address.')
    ])
    phone = StringField('Mobile Number', validators=[
        DataRequired(message='Please enter your 10-digit mobile number.'),
        Length(min=10, max=15, message='Please enter a valid mobile number.')
    ])
    password = PasswordField('Account Password', validators=[
        DataRequired(message='Please create a secure password.'),
        Length(min=8, message='Password must be at least 8 characters long.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password.'),
        EqualTo('password', message='Passwords must match.')
    ])

    # Step 2: Academic Information
    college_id = SelectField('College / Institution', coerce=int, validators=[
        DataRequired(message='Please select your college.')
    ])
    department_id = SelectField('Department / Discipline', coerce=int, validators=[
        DataRequired(message='Please select your department.')
    ])
    degree = SelectField('Degree Program', choices=[
        ('B.Tech / B.E', 'B.Tech / B.E (Engineering)'),
        ('B.Sc', 'B.Sc (Computer Science / IT / Science)'),
        ('BCA', 'BCA (Computer Applications)'),
        ('M.Tech / M.E', 'M.Tech / M.E (Postgraduate)'),
        ('MCA', 'MCA (Master of Computer Applications)'),
        ('M.Sc', 'M.Sc (Information Technology / Data Science)'),
        ('Other', 'Other Recognized Degree')
    ], validators=[DataRequired()])
    roll_number = StringField('Roll Number / Student ID', validators=[
        DataRequired(message='Please enter your college roll number or student ID.')
    ])
    current_year = SelectField('Current Year of Study', choices=[
        ('1st Year', '1st Year'),
        ('2nd Year', '2nd Year'),
        ('3rd Year', '3rd Year'),
        ('4th Year / Final Year', '4th Year / Final Year'),
        ('Recent Graduate', 'Recent Graduate (Alumni)')
    ], validators=[DataRequired()])
    graduation_year = SelectField('Graduation Year', choices=[
        ('2025', '2025'),
        ('2026', '2026'),
        ('2027', '2027'),
        ('2028', '2028'),
        ('2029', '2029')
    ], validators=[DataRequired()])

    # Step 3: Internship Plan
    plan_code = SelectField('Selected Internship Track', choices=[
        ('1_MONTH_PROJECT', 'Plan A — 1 Month Project Internship (INR 1,499)'),
        ('3_MONTH_PROFESSIONAL', 'Plan B — 3 Month Professional Internship (INR 3,999)')
    ], validators=[DataRequired()])

    # Step 4: Consent & Terms
    consent_agreed = BooleanField('I agree to the Terms & Conditions and consent to personal-data processing for internship verification and certificate issuance.', validators=[
        DataRequired(message='You must agree to the Anti Matrix Internship Terms to proceed.')
    ])

    submit = SubmitField('Complete Registration & Proceed')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data.lower()).first()
        if user:
            raise ValidationError('An account with this email address already exists. Please sign in instead.')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Registered Email Address', validators=[
        DataRequired(message='Please enter your registered email.'),
        Email(message='Please enter a valid email address.')
    ])
    submit = SubmitField('Send Password Reset Instructions')
