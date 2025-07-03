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
        recipients=[to],
        html=template,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    if current_app.config['MAIL_USERNAME']:
        thr = threading.Thread(target=send_async_email, args=[app, msg])
        thr.start()
        return thr
    else:
        
        current_app.logger.info(f'Email would be sent to {to}: {subject}')

def send_otp_email(user, otp_code):
    html_content = render_template('emails/otp_email.html', user=user, otp_code=otp_code)
    send_email(
        to=user.email,
        subject='Your OTP Code for Login Verification',
        template=html_content
    )

def send_welcome_email(user):
    html_content = render_template('emails/welcome_email.html', user=user)
    send_email(user.email, 'Welcome to HealneX', html_content)
