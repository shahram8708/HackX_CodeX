from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, HiddenField, StringField
from wtforms.validators import DataRequired

class SubscriptionForm(FlaskForm):
    plan_type = SelectField('Subscription Plan', choices=[
        ('monthly', 'Monthly Plan - 29.99/month'),
        ('annual', 'Annual Plan - 299.99/year (Save 17%)')
    ], validators=[DataRequired()])
    submit = SubmitField('Subscribe')

class PaymentForm(FlaskForm):
    payment_method_id = HiddenField('Payment Method ID', validators=[DataRequired()])
    submit = SubmitField('Complete Payment')

class CheckoutForm(FlaskForm):
    
    appointment_id = HiddenField('Appointment ID')
    submit = SubmitField('Pay Now')
