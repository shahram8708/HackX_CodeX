from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField, TimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional
from wtforms.widgets import TextArea
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class PatientRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=1, max=120)])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=20)])
    allergies = TextAreaField('Allergies (if any)', validators=[Optional()])
    conditions = TextAreaField('Medical Conditions (if any)', validators=[Optional()])
    emergency_contact = StringField('Emergency Contact', validators=[DataRequired(), Length(min=2, max=100)])
    referral_code = StringField('Referral Code (Optional)', validators=[Optional()])
    submit = SubmitField('Register as Patient')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class DoctorRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    specialization = StringField('Specialization', validators=[DataRequired(), Length(min=2, max=100)])
    license_number = StringField('License Number', validators=[DataRequired(), Length(min=5, max=50)])
    clinic_hospital = StringField('Clinic/Hospital Name', validators=[DataRequired(), Length(min=2, max=200)])
    consultation_fee = IntegerField('Consultation Fee ()', validators=[DataRequired(), NumberRange(min=1)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=20)])
    working_hours_start = TimeField('Working Hours Start', validators=[DataRequired()])
    working_hours_end = TimeField('Working Hours End', validators=[DataRequired()])
    working_days = SelectField('Working Days', 
                              choices=[('mon-fri', 'Monday to Friday'), 
                                     ('mon-sat', 'Monday to Saturday'), 
                                     ('all-days', 'All Days')], 
                              validators=[DataRequired()])
    submit = SubmitField('Register as Doctor')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')
    
    def validate_license_number(self, license_number):
        doctor = User.query.filter_by(license_number=license_number.data).first()
        if doctor:
            raise ValidationError('License number already registered.')

class OTPVerificationForm(FlaskForm):
    otp = StringField('OTP Code', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Reset Password')
