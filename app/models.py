from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
import random
import string

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text)
    role = db.Column(db.String(20), nullable=False)  
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    
    otp_code = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
    
    
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    allergies = db.Column(db.Text)
    conditions = db.Column(db.Text)
    emergency_contact = db.Column(db.String(100))
    unique_patient_id = db.Column(db.String(20), unique=True)
    referral_code = db.Column(db.String(20), unique=True)
    
    
    specialization = db.Column(db.String(100))
    license_number = db.Column(db.String(50))
    clinic_hospital = db.Column(db.String(200))
    consultation_fee = db.Column(db.Float)
    working_hours_start = db.Column(db.Time)
    working_hours_end = db.Column(db.Time)
    working_days = db.Column(db.String(50))  
    
    
    subscription_plan = db.Column(db.String(20))  
    subscription_expiry = db.Column(db.DateTime)
    subscription_active = db.Column(db.Boolean, default=False)
    subscription_tier = db.Column(db.String(20))
    
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    payments = db.relationship('Payment', backref='user', lazy='dynamic')
    medical_files = db.relationship('MedicalFile', foreign_keys='MedicalFile.patient_id', backref='patient', lazy='dynamic')
    uploaded_files = db.relationship('MedicalFile', foreign_keys='MedicalFile.doctor_id', backref='doctor', lazy='dynamic')
    
    
    patient_appointments = db.relationship('Appointment', foreign_keys='Appointment.patient_id', backref='patient', lazy='dynamic')
    
    
    doctor_appointments = db.relationship('Appointment', foreign_keys='Appointment.doctor_id', backref='doctor', lazy='dynamic')
    
    
    referred_users = db.relationship('Referral', foreign_keys='Referral.referrer_id', backref='referrer', lazy='dynamic')
    referrer_relationships = db.relationship('Referral', foreign_keys='Referral.referred_user_id', backref='referred_user', lazy='dynamic')
    
    
    sent_doctor_referrals = db.relationship('DoctorReferral', foreign_keys='DoctorReferral.from_doctor_id', backref='from_doctor', lazy='dynamic')
    received_doctor_referrals = db.relationship('DoctorReferral', foreign_keys='DoctorReferral.to_doctor_id', backref='to_doctor', lazy='dynamic')
    bank_account_number = db.Column(db.String(30))
    ifsc_code = db.Column(db.String(20))
    account_holder_name = db.Column(db.String(100))
    bank_name = db.Column(db.String(100))
    payout_enabled = db.Column(db.Boolean, default=False)
    stripe_account_id = db.Column(db.String(100))
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role == 'patient' and not self.unique_patient_id:
            self.unique_patient_id = self.generate_unique_patient_id()
        if self.role == 'patient' and not self.referral_code:
            self.referral_code = self.generate_referral_code()
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_otp(self):
        self.otp_code = ''.join(random.choices(string.digits, k=6))
        self.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        return self.otp_code
    
    def verify_otp(self, otp):
        if self.otp_code == otp and self.otp_expiry > datetime.utcnow():
            self.is_verified = True
            self.otp_code = None
            self.otp_expiry = None
            return True
        return False
    
    @staticmethod
    def generate_unique_patient_id():
        while True:
            patient_id = 'HC-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not User.query.filter_by(unique_patient_id=patient_id).first():
                return patient_id
    
    @staticmethod
    def generate_referral_code():
        while True:
            referral_code = 'REF-HC-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not User.query.filter_by(referral_code=referral_code).first():
                return referral_code
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'phone': self.phone,
            'unique_patient_id': self.unique_patient_id if self.role == 'patient' else None,
            'specialization': self.specialization if self.role == 'doctor' else None,
            'consultation_fee': self.consultation_fee if self.role == 'doctor' else None
        }

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_type = db.Column(db.String(20), nullable=False)  
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='pending')  
    notes = db.Column(db.Text)
    payment_method = db.Column(db.String(20), nullable=True)
    prescription = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reason = db.Column(db.Text)
    treatment_type = db.Column(db.String(50))
    attached_file = db.Column(db.String(200))
    
    payment = db.relationship('Payment', backref='appointment', uselist=False)
    
    def __repr__(self):
        return f'<Appointment {self.id}: {self.patient.name} with {self.doctor.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient_name': self.patient.name,
            'doctor_name': self.doctor.name,
            'appointment_type': self.appointment_type,
            'appointment_date': self.appointment_date.strftime('%Y-%m-%d'),
            'appointment_time': self.appointment_time.strftime('%H:%M'),
            'status': self.status,
            'notes': self.notes
        }

class MedicalFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer)
    ai_analysis = db.Column(db.Text)
    report_type = db.Column(db.String(100))  
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<MedicalFile {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.original_filename,
            'report_type': self.report_type,
            'description': self.description,
            'upload_date': self.upload_date.strftime('%Y-%m-%d %H:%M'),
            'doctor_name': self.doctor.name,
            'file_size': self.file_size
        }

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Message {self.id}: {self.sender.name} to {self.receiver.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.name,
            'sender_role': self.sender.role,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.name,
            'content': self.content,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': self.is_read
        }

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_type = db.Column(db.String(20), nullable=False)  
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='FI')
    status = db.Column(db.String(20), default='pending')  
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    stripe_payment_intent_id = db.Column(db.String(100))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'))
    
    
    plan_name = db.Column(db.String(50))
    plan_duration = db.Column(db.String(20))  
    
    def __repr__(self):
        return f'<Payment {self.id}: {self.amount} {self.payment_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'payment_type': self.payment_type,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'payment_date': self.payment_date.strftime('%Y-%m-%d %H:%M'),
            'plan_name': self.plan_name,
            'appointment_id': self.appointment_id
        }

class PayoutRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(200))  
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'link': self.link
        }

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referral_code_used = db.Column(db.String(20), nullable=False)
    points_awarded = db.Column(db.Integer, default=100)
    date_referred = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')  
    
    def __repr__(self):
        return f'<Referral {self.id}: {self.referrer.name} referred {self.referred_user.name}>'

class DoctorReferral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  
    referral_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    patient = db.relationship('User', foreign_keys=[patient_id], backref='doctor_referrals_as_patient')
    
    def __repr__(self):
        return f'<DoctorReferral {self.id}: {self.from_doctor.name} to {self.to_doctor.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'from_doctor_name': self.from_doctor.name,
            'to_doctor_name': self.to_doctor.name,
            'patient_name': self.patient.name,
            'reason': self.reason,
            'status': self.status,
            'referral_date': self.referral_date.strftime('%Y-%m-%d %H:%M')
        }

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=True)

    @staticmethod
    def get(key, default=None):
        setting = Setting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = Setting(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()

    @staticmethod
    def get_all_as_dict():
        return {s.key: s.value for s in Setting.query.all()}
