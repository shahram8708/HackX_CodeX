from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField, StringField, DateField
from wtforms.validators import DataRequired, Length, Optional
from app.models import User


class DoctorReferralForm(FlaskForm):
    patient_id = StringField('Patient ID', validators=[DataRequired(), Length(min=5, max=20)])
    to_doctor_id = SelectField('Refer to Doctor', choices=[], validators=[DataRequired()])
    reason = TextAreaField('Reason for Referral', validators=[DataRequired(), Length(min=10, max=500)])
    notes = TextAreaField('Additional Notes', validators=[Optional(), Length(max=500)])
    urgency = SelectField('Urgency', choices=[
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], validators=[DataRequired()])
    preferred_date = DateField('Preferred Appointment Date', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Send Referral')
    
    def __init__(self, *args, **kwargs):
        super(DoctorReferralForm, self).__init__(*args, **kwargs)
        
        doctors = User.query.filter_by(role='doctor', is_active=True).all()
        self.to_doctor_id.choices = [(str(doc.id), f'Dr. {doc.name} - {doc.specialization}') for doc in doctors]

class ReferralResponseForm(FlaskForm):
    status = SelectField('Response', choices=[
        ('accepted', 'Accept Referral'),
        ('completed', 'Mark as Completed')
    ], validators=[DataRequired()])
    notes = TextAreaField('Response Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Update Referral')
