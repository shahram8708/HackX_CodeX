from flask_mail import Message
from flask import current_app, render_template
from app import mail
import threading

def send_async_email(app, msg):
    
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send email: {str(e)}')

def send_email(to, subject, template, **kwargs):
    
    app = current_app._get_current_object()
    msg = Message(
        subject=f'[HealneX] {subject}',
        recipients=[to] if isinstance(to, str) else to,
        html=template,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    if current_app.config.get('MAIL_USERNAME'):
        thr = threading.Thread(target=send_async_email, args=[app, msg])
        thr.start()
        return thr
    else:
        
        current_app.logger.info(f'Email would be sent to {to}: {subject}')

def send_appointment_confirmation(appointment):
    

    
    patient_html = render_template('emails/appointment_confirmation.html', appointment=appointment)
    send_email(
        appointment.patient.email,
        'Appointment Confirmation',
        patient_html
    )

    
    doctor_html = render_template('emails/doctor_appointment_notification.html', appointment=appointment)
    send_email(
        appointment.doctor.email,
        'New Appointment Booked',
        doctor_html
    )

def send_payment_receipt(payment):
    
    html_content = render_template('emails/payment_receipt.html', payment=payment)
    send_email(
        payment.user.email,
        'Payment Receipt',
        html_content
    )

def send_referral_notification(referral):
    
    html_content = render_template('emails/referral_notification.html', referral=referral)
    send_email(
        referral.to_doctor.email,
        'New Patient Referral',
        html_content
    )
