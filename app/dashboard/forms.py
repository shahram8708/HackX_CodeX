from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, IntegerField, SelectField, FloatField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Email
from app.models import User

class EditPatientProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=20)])
    allergies = TextAreaField('Allergies', validators=[Optional()])
    conditions = TextAreaField('Medical Conditions', validators=[Optional()])
    emergency_contact = StringField('Emergency Contact', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Update Profile')

class EditDoctorProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[Optional(), Length(min=10, max=20)])
    specialization = StringField('Specialization', validators=[Optional()])
    license_number = StringField('License Number', validators=[Optional()])
    clinic_hospital = StringField('Clinic/Hospital', validators=[Optional()])
    consultation_fee = FloatField('Consultation Fee', validators=[Optional()])
    
    
    
    
    
    

    submit = SubmitField('Update Profile')


class EditAdminProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    phone = StringField('Phone Number')
    submit = SubmitField('Update')

class PatientLookupForm(FlaskForm):
    patient_id = StringField('Patient ID', validators=[DataRequired(), Length(min=5, max=20)])
    submit = SubmitField('Search Patient')

class AddTreatmentForm(FlaskForm):
    diagnosis = TextAreaField('Diagnosis', validators=[DataRequired()])
    prescription = TextAreaField('Prescription', validators=[DataRequired()])
    notes = TextAreaField('Additional Notes', validators=[Optional()])
    submit = SubmitField('Add Treatment Record')

class ContactSupportForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Your Email', validators=[DataRequired(), Email()])
    category = SelectField('Category', choices=[
        ('general', 'General Inquiry'),
        ('feedback', 'Feedback'),
        ('bug', 'Bug Report'),
        ('billing', 'Billing Issue'),
        ('technical', 'Technical Support')
    ], validators=[DataRequired()])
    message = TextAreaField('Your Message', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Send Message')
