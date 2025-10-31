from flask import render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from app import db
from app.dashboard import bp
from app.dashboard.forms import EditPatientProfileForm, EditDoctorProfileForm, PatientLookupForm, AddTreatmentForm, EditAdminProfileForm, ContactSupportForm
from app import mail
from flask_mail import Message as MailMessage
from app.models import User, Appointment, MedicalFile, Payment, Message, Notification, DoctorReferral, Referral
from sqlalchemy import func
from app.utils.decorators import patient_required, doctor_required
from app.utils.helpers import create_notification
from datetime import datetime, timedelta
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from datetime import datetime
import os

@bp.route('/dashboard/patient')
@login_required
@patient_required
def patient_dashboard():
    from datetime import date
    today = date.today()
    from sqlalchemy import or_, and_

    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        or_(
            and_(
                Appointment.payment_method == 'offline'
            ),
            Appointment.status == 'confirmed'
        ),
        Appointment.appointment_date >= today
    ).all()

    
    recent_consultations = Appointment.query.filter_by(
        patient_id=current_user.id,
        status='completed'
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    
    
    medical_files = MedicalFile.query.filter_by(
        patient_id=current_user.id
    ).order_by(MedicalFile.upload_date.desc()).limit(5).all()
    
    
    recent_messages = Message.query.filter_by(
        receiver_id=current_user.id,
        is_read=False
    ).order_by(Message.timestamp.desc()).limit(5).all()
    
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()

    recent_treatments = Appointment.query.filter_by(
        patient_id=current_user.id,
        status='completed'
    ).order_by(Appointment.updated_at.desc()).limit(3).all()

    total_points = db.session.query(
        func.sum(Referral.points_awarded)
    ).filter_by(referrer_id=current_user.id).scalar() or 0
    return render_template('dashboard/patient_dashboard.html',
                         upcoming_appointments=upcoming_appointments,
                         recent_consultations=recent_consultations,
                         medical_files=medical_files,
                         recent_messages=recent_messages,
                         notifications=notifications,
                         recent_treatments=recent_treatments,
                         total_points=total_points)
from datetime import date

@bp.route('/dashboard/doctor')
@login_required
@doctor_required
def doctor_dashboard():
    
    today = datetime.now().date()
    todays_appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        appointment_date=today
    ).order_by(Appointment.appointment_time.asc()).all()
    
    
    upcoming_appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        status='confirmed'
    ).filter(
        Appointment.appointment_date > today
    ).order_by(Appointment.appointment_date.asc()).limit(5).all()
    
    recent_patients = db.session.query(User, Appointment.created_at).join(
        Appointment, Appointment.patient_id == User.id
    ).filter(
        Appointment.doctor_id == current_user.id,
        Appointment.status.in_(['completed', 'confirmed'])
    ).order_by(Appointment.created_at.desc()).limit(10).all()

    recent_patients = [u for u, _ in recent_patients]

    total_patients = db.session.query(User.id).join(
        Appointment, Appointment.patient_id == User.id
    ).filter(
        Appointment.doctor_id == current_user.id
    ).distinct().count()
    from datetime import date
    today = date.today()
    from sqlalchemy import or_, and_

    upcoming_count = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        or_(
            and_(
                Appointment.payment_method == 'offline'
            ),
            Appointment.status == 'confirmed'
        ),
        Appointment.appointment_date >= today
    ).count()

    this_month_start = datetime.now().replace(day=1)
    monthly_earnings = db.session.query(db.func.sum(User.consultation_fee)).join(Appointment, Appointment.doctor_id == User.id).filter(
        Appointment.doctor_id == current_user.id,
        Appointment.status.in_(['completed']),
        Appointment.appointment_date >= this_month_start
    ).scalar() or 0

    payout_percentage = 0.80  

    total_earnings = (
        db.session.query(
            db.func.sum(User.consultation_fee * payout_percentage)
        )
        .join(Appointment, Appointment.doctor_id == User.id)
        .filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status.in_(['completed'])
        )
        .scalar()
    ) or 0

    
    recent_messages = Message.query.filter_by(
        receiver_id=current_user.id,
        is_read=False
    ).order_by(Message.timestamp.desc()).limit(5).all()
    
    
    received_referrals = DoctorReferral.query.filter_by(
        to_doctor_id=current_user.id,
        status='pending'
    ).order_by(DoctorReferral.referral_date.desc()).limit(5).all()

    lookup_form = PatientLookupForm()
    
    total_prescriptions = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.prescription.isnot(None),
        Appointment.prescription != ''
    ).count()
    
    return render_template('dashboard/doctor_dashboard.html',
                         today_appointments=todays_appointments,
                         upcoming_appointments=upcoming_appointments,
                         recent_patients=recent_patients,
                         total_patients=total_patients,
                         upcoming_count=upcoming_count,
                         monthly_earnings=monthly_earnings,
                         recent_messages=recent_messages,
                         received_referrals=received_referrals,lookup_form=lookup_form,
                         total_prescriptions=total_prescriptions,
                         total_earnings=total_earnings)

@bp.route('/patient/lookup', methods=['GET', 'POST'])
@login_required
@doctor_required
def patient_lookup():
    form = PatientLookupForm()
    patient_data = None
    
    if form.validate_on_submit():
        patient = User.query.filter_by(
            unique_patient_id=form.patient_id.data,
            role='patient'
        ).first()
        
        if patient:
            
            appointments = Appointment.query.filter_by(
                patient_id=patient.id
            ).order_by(Appointment.appointment_date.desc()).all()
            
            medical_files = MedicalFile.query.filter_by(
                patient_id=patient.id
            ).order_by(MedicalFile.upload_date.desc()).all()
            
            patient_data = {
                'patient': patient,
                'appointments': appointments,
                'medical_files': medical_files
            }
        else:
            flash('Patient not found. Please check the Patient ID.', 'warning')
    
    return render_template(
        'dashboard/patient_lookup.html',
        form=form,
        patient=patient_data['patient'] if patient_data else None,
        appointments=patient_data['appointments'] if patient_data else [],
        medical_files=patient_data['medical_files'] if patient_data else [],
        searched=True if form.validate_on_submit() else False,
        searched_id=form.patient_id.data if form.validate_on_submit() else None
    )

@bp.route('/patient/profile/<string:patient_id>')
@login_required
@doctor_required
def view_patient_profile(patient_id):
    patient = User.query.filter_by(unique_patient_id=patient_id, role='patient').first_or_404()

    appointments = Appointment.query.filter_by(
        patient_id=patient.id,
        doctor_id=current_user.id,
    ).order_by(Appointment.appointment_date.desc()).all()

    medical_files = MedicalFile.query.filter_by(
        patient_id=patient.id
    ).order_by(MedicalFile.upload_date.desc()).all()

    treatments = Appointment.query.filter_by(
        patient_id=patient.id,
        status='completed'
    ).order_by(Appointment.updated_at.desc()).all()

    return render_template('dashboard/patient_profile.html',
                           patient=patient,
                           appointments=appointments,
                           medical_files=medical_files,
                           treatments=treatments)

def get_patient_storage_used(patient_id):
    
    total_size = db.session.query(db.func.sum(MedicalFile.file_size)).filter_by(patient_id=patient_id).scalar() or 0
    return total_size / (1024 * 1024)  

@bp.route('/patient/add_treatment/<string:patient_id>', methods=['GET', 'POST'])
@login_required
@doctor_required
def add_treatment(patient_id):
    patient = User.query.filter_by(unique_patient_id=patient_id, role='patient').first()
    if not patient:
        abort(404)

    form = AddTreatmentForm()  

    if request.method == 'POST':
        treatment_type = request.form.get('treatment_type')
        title = request.form.get('title')
        description = request.form.get('description')
        medications = request.form.get('medications')
        file = request.files.get('file')

        
        appointment = Appointment.query.filter_by(
            patient_id=patient.id,
            doctor_id=current_user.id,
            status='confirmed'
        ).order_by(Appointment.appointment_date.desc()).first()

        if appointment:
            appointment.treatment_type = treatment_type
            appointment.diagnosis = description
            appointment.prescription = medications
            appointment.notes = title
            appointment.updated_at = datetime.utcnow()

            if file and file.filename != '':
                
                subscription_tier = patient.subscription_tier or 'free'
                subscription_plan = patient.subscription_plan or 'monthly'
                subscription_expiry = patient.subscription_expiry
                subscription_active = patient.subscription_active

                
                if subscription_tier != 'free':
                    if not subscription_active or not subscription_expiry or subscription_expiry < datetime.utcnow():
                        flash("Patient's subscription has expired. Please ask them to renew.", "danger")
                        return redirect(url_for('dashboard.view_patient_profile', patient_id=patient.unique_patient_id))

                
                filename = secure_filename(file.filename)
                folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'treatments')
                os.makedirs(folder, exist_ok=True)
                filepath = os.path.join(folder, filename)

                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                used_mb = get_patient_storage_used(patient.id)
                file_size_mb = file_size / (1024 * 1024)

                limits = {
                    'free': 100,
                    'basic': 1024,
                    'premium': 10240,
                    'enterprise': float('inf')
                }
                plan_key = subscription_tier.strip().lower()
                if plan_key not in limits:
                    plan_key = 'free'
                allowed_mb = limits[plan_key]

                if used_mb + file_size_mb > allowed_mb:
                    flash(f'Storage limit exceeded. This patient\'s subscription allows up to {allowed_mb}MB of storage.', 'danger')
                    return redirect(url_for('dashboard.view_patient_profile', patient_id=patient.unique_patient_id))

                
                file.save(filepath)
                appointment.attached_file = filename

            
            create_notification(
                patient.id,
                'Treatment Record Updated',
                f'Dr. {current_user.name} has updated your treatment record.',
                'appointment',
                url_for('dashboard.patient_dashboard')
            )

            db.session.commit()
            flash('Treatment record added successfully!', 'success')
        else:
            flash('No active appointment found for this patient.', 'warning')

        return redirect(url_for('dashboard.view_patient_profile', patient_id=patient.unique_patient_id))

    return render_template('dashboard/add_treatment.html', form=form, patient=patient)

@bp.route('/treatment-history')
@login_required
@patient_required
def treatment_history():
    try:
        
        page = request.args.get('page', 1, type=int)
        per_page = 9  
        
        treatments = Appointment.query.filter_by(
            patient_id=current_user.id,
            status='completed'
        ).order_by(
            Appointment.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        
        if page > treatments.pages and treatments.pages > 0:
            return redirect(url_for('dashboard.treatment_history', page=treatments.pages))
        
        return render_template(
            'dashboard/treatment_list.html',
            treatments=treatments
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading treatment history for user {current_user.id}: {str(e)}")
        flash('An error occurred while loading your treatment history. Please try again.', 'error')
        return redirect(url_for('dashboard.patient_dashboard'))

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = None

    if current_user.role == 'patient':
        form = EditPatientProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.name = form.name.data
            current_user.phone = form.phone.data
            current_user.allergies = form.allergies.data
            current_user.conditions = form.conditions.data
            current_user.emergency_contact = form.emergency_contact.data
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard.patient_dashboard'))
        
    elif current_user.role == 'doctor':
        form = EditDoctorProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.name = form.name.data
            current_user.phone = form.phone.data
            current_user.specialization = form.specialization.data
            current_user.clinic_hospital = form.clinic_hospital.data
            current_user.consultation_fee = form.consultation_fee.data
            
            if not current_user.stripe_account_id:
                flash("Please complete your Stripe onboarding to enable payouts.", "warning")
                return redirect(url_for('dashboard.onboard_stripe'))
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard.doctor_dashboard'))

    elif current_user.role == 'admin':
        form = EditAdminProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.name = form.name.data
            current_user.email = form.email.data
            current_user.phone = form.phone.data
            db.session.commit()
            flash('Admin profile updated successfully!', 'success')
            return redirect(url_for('admin.admin_dashboard'))

    return render_template('dashboard/edit_profile.html', form=form)

import stripe
@bp.route('/doctor/onboard/stripe')
@login_required
@doctor_required
def onboard_stripe():
    if not current_user.stripe_account_id:
        
        account = stripe.Account.create(
            type='express',
            country='IN',
            email=current_user.email,
            capabilities={
                'transfers': {'requested': True},
                'card_payments': {'requested': True}
            }
        )
        current_user.stripe_account_id = account.id
        db.session.commit()
    else:
        account = stripe.Account.retrieve(current_user.stripe_account_id)

    
    account_link = stripe.AccountLink.create(
        account=account.id,
        refresh_url=url_for('dashboard.onboard_stripe', _external=True),
        return_url=url_for('dashboard.onboard_stripe', _external=True),
        type='account_onboarding'
    )

    return redirect(account_link.url)

@bp.route('/doctor/onboard/success')
@login_required
@doctor_required
def onboard_success():
    flash('Stripe onboarding completed successfully!', 'success')
    return redirect(url_for('dashboard.doctor_dashboard'))

@bp.route('/api/quick_stats')
@login_required
def api_quick_stats():
    
    if current_user.role == 'patient':
        upcoming_count = Appointment.query.filter_by(
            patient_id=current_user.id,
            status='confirmed'
        ).filter(
            Appointment.appointment_date >= datetime.now().date()
        ).count()
        
        unread_messages = Message.query.filter_by(
            receiver_id=current_user.id,
            is_read=False
        ).count()
        
        return jsonify({
            'upcoming_appointments': upcoming_count,
            'unread_messages': unread_messages,
            'patient_id': current_user.unique_patient_id
        })
        
    elif current_user.role == 'doctor':
        today = datetime.now().date()
        todays_appointments = Appointment.query.filter_by(
            doctor_id=current_user.id,
            appointment_date=today
        ).count()
        
        pending_referrals = DoctorReferral.query.filter_by(
            to_doctor_id=current_user.id,
            status='pending'
        ).count()
        
        return jsonify({
            'todays_appointments': todays_appointments,
            'pending_referrals': pending_referrals
        })
    
    return jsonify({})

from app.utils.email import send_email

@bp.route('/support/contact', methods=['GET', 'POST'])
def contact_support():
    form = ContactSupportForm()
    
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        category = form.category.data
        message_body = form.message.data

        
        html_content = render_template(
            'emails/contact_support_email.html',
            name=name,
            email=email,
            category=category.title(),
            message=message_body
        )

        try:
            send_email(
                to=current_app.config['ADMIN_EMAIL'],
                subject=f"New Support Request - {category.title()}",
                template=html_content
            )
            flash("Your message has been sent successfully. We'll get back to you soon!", 'success')
            return redirect(url_for('dashboard.contact_support'))
        except Exception as e:
            current_app.logger.error(f"Error sending support email: {e}")
            flash("Something went wrong. Please try again later.", 'danger')

    return render_template('dashboard/contact_support.html', form=form)
