from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, PatientRegistrationForm, DoctorRegistrationForm, OTPVerificationForm
from app.auth.utils import send_otp_email, send_welcome_email
from app.models import User, Referral, Notification
from datetime import datetime

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))
            
            
            otp_code = user.generate_otp()
            db.session.commit()
            
            
            send_otp_email(user, otp_code)
            
            
            session['pending_user_id'] = user.id
            flash('An OTP has been sent to your email. Please verify to complete login.', 'info')
            return redirect(url_for('auth.verify_otp'))
        
        flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'pending_user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('auth.login'))
    
    form = OTPVerificationForm()
    if form.validate_on_submit():
        user = User.query.get(session['pending_user_id'])
        
        if user and user.verify_otp(form.otp.data):
            db.session.commit()
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            
            session.pop('pending_user_id', None)
            
            flash(f'Welcome back, {user.name}!', 'success')
            
            
            if user.role == 'patient':
                return redirect(url_for('dashboard.patient_dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('dashboard.doctor_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
        
        flash('Invalid or expired OTP. Please try again.', 'danger')
    
    return render_template('auth/verify_otp.html', title='Verify OTP', form=form)

@bp.route('/register/patient', methods=['GET', 'POST'])
def register_patient():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = PatientRegistrationForm()
    if form.validate_on_submit():
        
        referrer = None
        if form.referral_code.data:
            referrer = User.query.filter_by(referral_code=form.referral_code.data).first()
            if not referrer:
                flash('Invalid referral code.', 'warning')
        
        
        user = User(
            name=form.name.data,
            email=form.email.data,
            role='patient',
            age=form.age.data,
            gender=form.gender.data,
            phone=form.phone.data,
            allergies=form.allergies.data,
            conditions=form.conditions.data,
            emergency_contact=form.emergency_contact.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        
        if referrer:
            referral = Referral(
                referrer_id=referrer.id,
                referred_user_id=user.id,
                referral_code_used=form.referral_code.data,
                points_awarded=100
            )
            db.session.add(referral)
            
            
            notification = Notification(
                user_id=referrer.id,
                title='New Referral!',
                message=f'{user.name} joined using your referral code. You earned 100 points!',
                notification_type='referral'
            )
            db.session.add(notification)
            db.session.commit()
        
        
        send_welcome_email(user)
        
        flash(f'Registration successful! Your unique patient ID is: {user.unique_patient_id}', 'success')
        flash('Please check your email for welcome instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register as Patient', form=form, user_type='patient')

@bp.route('/register/doctor', methods=['GET', 'POST'])
def register_doctor():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = DoctorRegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data,
            role='doctor',
            specialization=form.specialization.data,
            license_number=form.license_number.data,
            clinic_hospital=form.clinic_hospital.data,
            consultation_fee=form.consultation_fee.data,
            phone=form.phone.data,
            working_hours_start=form.working_hours_start.data,
            working_hours_end=form.working_hours_end.data,
            working_days=form.working_days.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        
        send_welcome_email(user)
        
        flash('Doctor registration successful! Please login to continue.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register as Doctor', form=form, user_type='doctor')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/resend_otp')
def resend_otp():
    if 'pending_user_id' not in session:
        flash('Please login first.', 'warning')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['pending_user_id'])
    if user:
        otp_code = user.generate_otp()
        db.session.commit()
        send_otp_email(user, otp_code)
        flash('New OTP sent to your email.', 'info')
    
    return redirect(url_for('auth.verify_otp'))
