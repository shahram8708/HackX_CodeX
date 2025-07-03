from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, TextAreaField, SubmitField, StringField, DateField
from datetime import datetime
from wtforms.validators import DataRequired, Optional, Length

class UploadReportForm(FlaskForm):
    patient_id = StringField('Patient ID', validators=[DataRequired(), Length(min=5, max=20)])
    upload_date = DateField('Upload Date', format='%Y-%m-%d', default=datetime.utcnow)
    file = FileField('Medical File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 'Only PDF, images, and Word documents are allowed!')
    ])
    report_type = SelectField('Report Type', choices=[
        ('prescription', 'Prescription'),
        ('x-ray', 'X-Ray'),
        ('blood-test', 'Blood Test'),
        ('mri', 'MRI Scan'),
        ('ct-scan', 'CT Scan'),
        ('lab-report', 'Lab Report'),
        ('diagnosis', 'Diagnosis Report'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Upload Report')

class QuickUploadForm(FlaskForm):
    file = FileField('Medical File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'], 'Only PDF, images, and Word documents are allowed!')
    ])
    report_type = SelectField('Report Type', choices=[
        ('prescription', 'Prescription'),
        ('x-ray', 'X-Ray'),
        ('blood-test', 'Blood Test'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Upload')
