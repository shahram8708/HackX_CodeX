from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, TimeField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional
from datetime import datetime, timedelta

class BookAppointmentForm(FlaskForm):
    doctor_id = HiddenField('Doctor ID', validators=[DataRequired()])
    appointment_type = SelectField('Appointment Type', 
                                 choices=[('in-person', 'In-Person'), ('teleconsultation', 'Teleconsultation')],
                                 validators=[DataRequired()])
    appointment_date = DateField('Appointment Date', validators=[DataRequired()],
                               default=datetime.now().date() + timedelta(days=1))
    appointment_time = HiddenField('Appointment Time', validators=[DataRequired()])
    notes = TextAreaField('Additional Notes (Optional)', validators=[Optional()])
    payment_method = SelectField('Payment Method', choices=[
        ('online', 'Online'),
        ('offline', 'Offline')
    ], validators=[DataRequired()])
    reason = TextAreaField()
    submit = SubmitField('Book Appointment')

class RescheduleAppointmentForm(FlaskForm):
    appointment_date = DateField('New Appointment Date', validators=[DataRequired()])
    appointment_time = SelectField('New Appointment Time', choices=[], validate_choice=False)
    reason = TextAreaField('Reason for Rescheduling (Optional)')
    submit = SubmitField('Reschedule Appointment')

class SearchDoctorsForm(FlaskForm):
    specialization = SelectField('Specialization', choices=[('', 'All Specializations')], validators=[Optional()])
    name = TextAreaField('Doctor Name', validators=[Optional()])
    submit = SubmitField('Search')
