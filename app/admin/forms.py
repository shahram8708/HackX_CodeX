from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, BooleanField, FloatField, IntegerField, TimeField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from app.models import User

class EditUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('patient', 'Patient'), ('doctor', 'Doctor'), ('admin', 'Admin')])
    is_active = BooleanField('Active')
    is_verified = BooleanField('Verified')
    age = IntegerField('Age', validators=[Optional()])
    phone = StringField('Phone', validators=[Optional()])
    allergies = TextAreaField('Allergies', validators=[Optional()])
    medical_conditions = TextAreaField('Medical Conditions', validators=[Optional()])

    
    specialization = StringField('Specialization', validators=[Optional()])
    license_number = StringField('License Number', validators=[Optional()])
    clinic_hospital = StringField('Clinic/Hospital Name', validators=[Optional()])
    consultation_fee = FloatField('Consultation Fee', validators=[Optional()])

class SendAnnouncementForm(FlaskForm):
    send_to_all = BooleanField('All Users')
    send_to_patients = BooleanField('Patients')
    send_to_doctors = BooleanField('Doctors')

    announcement_type = SelectField(
        'Announcement Type',
        choices=[('general', 'General'), ('important', 'Important'), ('urgent', 'Urgent')],
        validators=[DataRequired()]
    )
    
    title = StringField('Title', validators=[DataRequired(), Length(min=3, max=100)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=5)])

    send_email = BooleanField('Also send via email')
    urgent = BooleanField('Mark as urgent')
    submit = SubmitField('Send Announcement')

class SystemSettingsForm(FlaskForm):
    site_name = StringField('Site Name', validators=[DataRequired(), Length(min=2, max=100)])
    admin_email = StringField('Admin Email', validators=[DataRequired(), Email()])
    max_file_size = FloatField('Max File Size (MB)', validators=[DataRequired(), NumberRange(min=1, max=100)])
    session_timeout = IntegerField('Session Timeout (minutes)', validators=[DataRequired(), NumberRange(min=15, max=480)])
    
    maintenance_mode = BooleanField('Maintenance Mode')
    registration_enabled = BooleanField('Allow New Registrations')
    
    smtp_server = StringField('SMTP Server', validators=[Length(max=100)])
    smtp_port = IntegerField('SMTP Port', validators=[NumberRange(min=1, max=65535)])
    email_notifications = BooleanField('Enable Email Notifications')
    
    submit = SubmitField('Save Settings')
