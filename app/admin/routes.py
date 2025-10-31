from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.admin import bp
from app.admin.forms import EditUserForm, SendAnnouncementForm, SystemSettingsForm
from app.models import User, Appointment, Payment, MedicalFile, Message, Notification, Referral, Setting
from app.utils.decorators import admin_required
from app.utils.helpers import create_notification
from datetime import datetime, timedelta
from sqlalchemy import func, text
import os
from app.utils.email import send_email

@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    
    user_growth = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).group_by(func.date(User.created_at)).order_by('date').all()

    
    revenue_growth = db.session.query(
        func.date(Payment.payment_date).label('date'),
        func.sum(Payment.amount).label('revenue')
    ).filter(Payment.status == 'completed').group_by(
        func.date(Payment.payment_date)
    ).order_by('date').all()
    total_users = User.query.count()
    total_patients = User.query.filter_by(role='patient').count()
    total_doctors = User.query.filter_by(role='doctor').count()
    doctors_count = total_doctors
    patients_count = total_patients
    admins_count = User.query.filter_by(role='admin').count()
    user_growth_labels = [datetime.strptime(row.date, '%Y-%m-%d').strftime('%b %d') if isinstance(row.date, str) else row.date.strftime('%b %d') for row in user_growth]
    user_growth_data = [row.count for row in user_growth]

    revenue_labels = [datetime.strptime(row.date, '%Y-%m-%d').strftime('%b %d') if isinstance(row.date, str) else row.date.strftime('%b %d') for row in revenue_growth]
    revenue_data = [float(row.revenue) for row in revenue_growth]

    
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(
        appointment_date=datetime.now().date()
    ).count()
    
    
    total_payments = Payment.query.filter_by(status='completed').count()
    PLATFORM_FEE = 2.99
    TAX_AMOUNT = 1.50
    TOTAL_PLATFORM_EARNING_PER_CONSULTATION = PLATFORM_FEE + TAX_AMOUNT  

    
    consultation_count = Payment.query.filter_by(
        payment_type='consultation',
        status='completed'
    ).count()

    
    consultation_revenue = consultation_count * TOTAL_PLATFORM_EARNING_PER_CONSULTATION

    
    subscription_revenue = db.session.query(
        func.sum(Payment.amount)
    ).filter(
        Payment.payment_type == 'subscription',
        Payment.status == 'completed'
    ).scalar() or 0

    
    total_revenue = round(consultation_revenue + subscription_revenue, 2)

    
    this_month_start = datetime.now().replace(day=1)
    this_month_users = User.query.filter(
        User.created_at >= this_month_start
    ).count()
    
    consultation_this_month_count = Payment.query.filter(
        Payment.payment_type == 'consultation',
        Payment.status == 'completed',
        Payment.payment_date >= this_month_start
    ).count()

    
    consultation_revenue_this_month = consultation_this_month_count * TOTAL_PLATFORM_EARNING_PER_CONSULTATION

    
    subscription_revenue_this_month = db.session.query(
        func.sum(Payment.amount)
    ).filter(
        Payment.payment_type == 'subscription',
        Payment.status == 'completed',
        Payment.payment_date >= this_month_start
    ).scalar() or 0

    
    revenue_this_month = round(consultation_revenue_this_month + subscription_revenue_this_month, 2)

    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_appointments = Appointment.query.order_by(
        Appointment.created_at.desc()
    ).limit(5).all()
    recent_payments = Payment.query.filter_by(
        status='completed'
    ).order_by(Payment.payment_date.desc()).limit(5).all()
    
    
    total_files = MedicalFile.query.count()
    total_messages = Message.query.count()
    unresolved_issues = 0  
    
    active_subscriptions = db.session.query(Payment.user_id).filter(
        Payment.payment_type == 'subscription',
        Payment.status == 'completed'
    ).distinct().count()

    
    subscription_conversion_rate = round((active_subscriptions / total_users) * 100, 2) if total_users > 0 else 0

    from collections import namedtuple

    Activity = namedtuple('Activity', ['timestamp', 'user', 'action_type', 'description'])

    recent_activities = []

    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    for user in recent_users:
        recent_activities.append(Activity(
            timestamp=user.created_at,
            user=user,
            action_type='register',
            description=f"{user.name} ({user.role}) registered."
        ))

    
    recent_payments = Payment.query.filter_by(status='completed').order_by(Payment.payment_date.desc()).limit(5).all()
    for payment in recent_payments:
        recent_activities.append(Activity(
            timestamp=payment.payment_date,
            user=payment.user,
            action_type='payment',
            description=f"{payment.user.name} paid {payment.amount} for {payment.payment_type}."
        ))

    
    recent_appts = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    for appt in recent_appts:
        recent_activities.append(Activity(
            timestamp=appt.created_at,
            user=appt.patient,
            action_type='appointment',
            description=f"{appt.patient.name} booked with Dr. {appt.doctor.name} ({appt.status})."
        ))

    
    recent_activities.sort(key=lambda x: x.timestamp, reverse=True)

    
    recent_activities = recent_activities[:10]
    
    top_doctors = db.session.query(
        User.id,
        User.name,
        User.specialization,
        func.count(Appointment.id).label('total_appointments')
    ).join(Appointment, Appointment.doctor_id == User.id
    ).filter(User.role == 'doctor'
    ).group_by(User.id, User.name, User.specialization
    ).order_by(func.count(Appointment.id).desc()
    ).limit(5).all()

    stats = {
        'total_users': total_users,
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_appointments': total_appointments,
        'today_appointments': today_appointments,
        'total_payments': total_payments,
        'total_revenue': float(total_revenue),
        'this_month_users': this_month_users,
        'this_month_revenue': float(revenue_this_month),
        'total_files': total_files,
        'total_messages': total_messages,
        'unresolved_issues': unresolved_issues,
        'doctors_count': doctors_count,
        'patients_count': patients_count,
        'admins_count': admins_count,
        'user_growth_labels': user_growth_labels,
        'user_growth_data': user_growth_data,
        'revenue_labels': revenue_labels,
        'revenue_data': revenue_data,
        'recent_users': recent_users,
        'recent_appointments': recent_appointments,
        'recent_payments': recent_payments
    }
    
    return render_template('admin/admin_dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_appointments=recent_appointments,
                         recent_payments=recent_payments,
                         doctors_count=doctors_count,
                         patients_count=patients_count,
                         admins_count=admins_count,
                         total_users=total_users,
                         user_growth_labels=user_growth_labels,
                         user_growth_data=user_growth_data,
                         revenue_labels=revenue_labels,
                         revenue_data=revenue_data,
                         active_subscriptions=active_subscriptions,
                         subscription_conversion_rate=subscription_conversion_rate,
                         recent_activities=recent_activities,
                         top_doctors=top_doctors)

@bp.route('/users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    search = request.args.get('search', '')
    per_page = 20
    
    
    query = User.query
    
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    if search:
        query = query.filter(
            (User.name.contains(search)) |
            (User.email.contains(search)) |
            (User.unique_patient_id.contains(search))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    total_patients = User.query.filter_by(role='patient').count()
    total_doctors = User.query.filter_by(role='doctor').count()
    active_users = User.query.filter_by(is_active=True).count()

    new_registrations_today = User.query.filter(
        User.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()

    return render_template('admin/admin_users.html', users=users,
                         role_filter=role_filter, search=search, total_patients=total_patients, total_doctors=total_doctors, active_users=active_users, new_registrations_today=new_registrations_today)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        user.is_verified = form.is_verified.data

        
        if user.role == 'doctor':
            user.specialization = form.specialization.data
            user.license_number = form.license_number.data
            user.clinic_hospital = form.clinic_hospital.data
            user.consultation_fee = form.consultation_fee.data

        
        elif user.role == 'patient':
            user.age = form.age.data
            user.phone = form.phone.data
            user.allergies = form.allergies.data
            user.conditions = form.medical_conditions.data  

        db.session.commit()

        create_notification(
            user.id,
            'Account Updated',
            'Your account information has been updated by an administrator.',
            'system'
        )

        flash(f'User {user.name} updated successfully!', 'success')
        return redirect(url_for('admin.manage_users'))

    return render_template('admin/edit_user.html', form=form, user=user)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == 'admin':
        flash('Cannot delete admin users.', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    
    user.is_active = False
    db.session.commit()
    
    flash(f'User {user.name} has been deactivated.', 'success')
    return redirect(url_for('admin.manage_users'))
 
@bp.route('/appointments')
@login_required
@admin_required
def manage_appointments():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    date_filter = request.args.get('date', '')
    per_page = 20
    search = request.args.get('search', '').strip()
    appointment_type = request.args.get('type', '')
    date_range = request.args.get('date_range', '')
        
    
    query = Appointment.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)

    if appointment_type:
        query = query.filter_by(appointment_type=appointment_type)

    if search:
        query = query.join(User, Appointment.patient).filter(
            User.name.ilike(f'%{search}%')
        )

    if date_range:
        today = datetime.utcnow().date()
        if date_range == 'today':
            query = query.filter(Appointment.appointment_date == today)
        elif date_range == 'week':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            query = query.filter(Appointment.appointment_date.between(start_week, end_week))
        elif date_range == 'month':
            start_month = today.replace(day=1)
            end_month = (start_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            query = query.filter(Appointment.appointment_date.between(start_month, end_month))

    appointments = query.order_by(Appointment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    total_appointments = Appointment.query.count()
    pending_appointments = Appointment.query.filter_by(status='pending').count()
    completed_appointments = Appointment.query.filter_by(status='completed').count()
    cancelled_appointments = Appointment.query.filter_by(status='cancelled').count()

    return render_template('admin/manage_appointments.html',
                         appointments=appointments,
                         status_filter=status_filter,
                         date_filter=date_filter,
                         total_appointments=total_appointments,
                         pending_appointments=pending_appointments,
                         completed_appointments=completed_appointments,
                         cancelled_appointments=cancelled_appointments)

@bp.route('/payments')
@login_required
@admin_required
def manage_payments():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '').strip()
    date_range = request.args.get('date_range', '')

    type_filter = request.args.get('type', '')
    per_page = 20
    
    from sqlalchemy import or_, and_
    from datetime import datetime, timedelta

    query = Payment.query.join(User)

    if status_filter:
        query = query.filter(Payment.status == status_filter)

    if type_filter:
        query = query.filter(Payment.payment_type == type_filter)

    if search:
        query = query.filter(or_(
            User.name.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%'),
            Payment.transaction_id.ilike(f'%{search}%')
        ))

    if date_range:
        today = datetime.utcnow().date()
        if date_range == 'today':
            query = query.filter(Payment.payment_date >= today)
        elif date_range == 'week':
            query = query.filter(Payment.payment_date >= today - timedelta(days=7))
        elif date_range == 'month':
            query = query.filter(Payment.payment_date >= today.replace(day=1))
        elif date_range == 'quarter':
            start_month = (today.month - 1) // 3 * 3 + 1
            quarter_start = today.replace(month=start_month, day=1)
            query = query.filter(Payment.payment_date >= quarter_start)

    payments = query.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    
    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
        status='completed'
    ).scalar() or 0
    
    pending_amount = db.session.query(func.sum(Payment.amount)).filter_by(
        status='pending'
    ).scalar() or 0

    consultation_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
        status='completed',
        payment_type='consultation'
    ).scalar() or 0

    
    subscription_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
        status='completed',
        payment_type='subscription'
    ).scalar() or 0
    
    failed_payments = Payment.query.filter_by(status='failed').count()

    return render_template('admin/manage_payments.html',
                         payments=payments,
                         total_revenue=float(total_revenue),
                         pending_amount=float(pending_amount),
                         status_filter=status_filter,
                         type_filter=type_filter,
                         consultation_revenue=float(consultation_revenue),
                         subscription_revenue=float(subscription_revenue),
                         failed_payments=failed_payments)

@bp.route('/files')
@login_required
@admin_required
def manage_files():
    page = request.args.get('page', 1, type=int)
    type_filter = request.args.get('type', '')
    per_page = 20
    
    
    query = MedicalFile.query
    
    if type_filter:
        query = query.filter_by(report_type=type_filter)
    
    files = query.order_by(MedicalFile.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    
    total_files = MedicalFile.query.count()
    total_size = db.session.query(func.sum(MedicalFile.file_size)).scalar() or 0
    
    return render_template('admin/manage_files.html',
                         files=files,
                         total_files=total_files,
                         total_size=total_size,
                         type_filter=type_filter)

@bp.route('/referrals')
@login_required
@admin_required
def manage_referrals():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    
    patient_referrals = Referral.query.order_by(
        Referral.date_referred.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    
    total_patient_referrals = Referral.query.count()
    total_points_awarded = db.session.query(func.sum(Referral.points_awarded)).scalar() or 0
    
    successful_referrals = Referral.query.filter(Referral.referred_user_id.isnot(None)).count()
    pending_referrals = Referral.query.filter(Referral.referred_user_id.is_(None)).count()

    return render_template('admin/manage_referrals.html',
                         patient_referrals=patient_referrals,
                         total_patient_referrals=total_patient_referrals,
                         total_points_awarded=total_points_awarded,
                         successful_referrals=successful_referrals,
                         pending_referrals=pending_referrals)

@bp.route('/announcements', methods=['GET', 'POST'])
@login_required
@admin_required
def send_announcement():
    form = SendAnnouncementForm()
    
    if form.validate_on_submit():
        users = []

        if form.send_to_all.data:
            users = User.query.filter_by(is_active=True).all()
        else:
            if form.send_to_patients.data:
                users += User.query.filter_by(role='patient', is_active=True).all()
            if form.send_to_doctors.data:
                users += User.query.filter_by(role='doctor', is_active=True).all()

        
        users = list(set(users))

        
        notification_count = 0
        for user in users:
            
            create_notification(
                user.id,
                form.title.data,
                form.message.data,
                'system'
            )
            
            
            if form.send_email.data:
                email_html = render_template(
                    'emails/generic_announcement.html',
                    user=user,
                    title=form.title.data,
                    message=form.message.data
                )
                send_email(
                    to=user.email,
                    subject=form.title.data,
                    template=email_html
                )

            notification_count += 1

        flash(f'Announcement sent to {notification_count} users!', 'success')
        return redirect(url_for('admin.admin_dashboard'))

    recent_announcements = (
        db.session.query(
            Notification.title,
            Notification.message,
            Notification.notification_type.label('announcement_type'),
            func.count(Notification.id).label('recipient_count'),
            func.max(Notification.created_at).label('created_at')
        )
        .filter(Notification.notification_type == 'system')
        .group_by(Notification.title, Notification.message, Notification.notification_type)
        .order_by(func.max(Notification.created_at).desc())
        .limit(5)
        .all()
    )

    return render_template('admin/send_announcement.html', form=form, recent_announcements=recent_announcements)

@bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    
    
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    new_users_today = User.query.filter(
        User.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    
    total_appointments = Appointment.query.count()
    today_appointments = Appointment.query.filter_by(
        appointment_date=datetime.now().date()
    ).count()
    
    
    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
        status='completed'
    ).scalar() or 0
    
    this_month_start = datetime.now().replace(day=1)
    this_month_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.payment_date >= this_month_start
    ).scalar() or 0
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'new_users_today': new_users_today,
        'total_appointments': total_appointments,
        'today_appointments': today_appointments,
        'total_revenue': float(total_revenue),
        'this_month_revenue': float(this_month_revenue)
    })

from sqlalchemy import text

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_file_storage_usage_percent():
    try:
        db_path = os.path.join(os.path.dirname(current_app.root_path), 'instance', 'healnex.db')
        total_bytes = os.path.getsize(db_path)
        
        used_mb = total_bytes / (1024 * 1024)
        max_limit_mb = 500 
        usage_percent = (used_mb / max_limit_mb) * 100
        return round(usage_percent, 2)
    except Exception as e:
        return f"Error: {str(e)}"
    
@bp.route('/reports')
@login_required
@admin_required
def system_reports():
    

    from sqlalchemy import text

    
    user_growth = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).group_by(func.date(User.created_at)).order_by('date').all()

    user_registration_labels = [
        datetime.strptime(row.date, '%Y-%m-%d').strftime('%b %d') if isinstance(row.date, str) else row.date.strftime('%b %d')
        for row in user_growth
    ]
    user_registration_data = [row.count for row in user_growth]

    
    revenue_growth = db.session.query(
        func.date(Payment.payment_date).label('date'),
        func.sum(Payment.amount).label('revenue')
    ).filter_by(status='completed').group_by(func.date(Payment.payment_date)).order_by('date').all()

    revenue_labels = [
        datetime.strptime(row.date, '%Y-%m-%d').strftime('%b %d') if isinstance(row.date, str) else row.date.strftime('%b %d')
        for row in revenue_growth
    ]
    revenue_data = [float(row.revenue) for row in revenue_growth]

    
    total_users = User.query.count()
    new_users_this_month = User.query.filter(User.created_at >= datetime.now().replace(day=1)).count()

    total_appointments = Appointment.query.count()
    completed_appointments = Appointment.query.filter_by(status='completed').count()

    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.payment_date >= datetime.now().replace(day=1)
    ).scalar() or 0

    active_subscriptions = db.session.query(Payment.user_id).filter_by(
        status='completed',
        payment_type='subscription'
    ).distinct().count()
    subscription_conversion = round((active_subscriptions / total_users) * 100, 2) if total_users else 0

    
    pending_appointments = Appointment.query.filter_by(status='pending').count()
    confirmed_appointments = Appointment.query.filter_by(status='confirmed').count()
    cancelled_appointments = Appointment.query.filter_by(status='cancelled').count()

    
    doctor_count = User.query.filter_by(role='doctor').count()
    patient_count = User.query.filter_by(role='patient').count()
    admin_count = User.query.filter_by(role='admin').count()

    
    top_doctors = db.session.query(
        User.id,
        User.name,
        User.specialization,
        func.count(Appointment.id).label('appointment_count')
    ).join(Appointment, User.id == Appointment.doctor_id
    ).group_by(User.id, User.name, User.specialization
    ).order_by(text('appointment_count desc')).limit(10).all()

    
    database_health = 100
    file_storage_usage = get_file_storage_usage_percent()
    email_delivery_rate = 100
    api_uptime = 100

    
    from collections import namedtuple

    Activity = namedtuple('Activity', ['timestamp', 'user', 'action_type', 'description'])

    recent_activities = []

    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    for user in recent_users:
        recent_activities.append(Activity(
            timestamp=user.created_at,
            user=user,
            action_type='register',
            description=f"{user.name} ({user.role}) registered."
        ))

    
    recent_payments = Payment.query.filter_by(status='completed').order_by(Payment.payment_date.desc()).limit(5).all()
    for payment in recent_payments:
        recent_activities.append(Activity(
            timestamp=payment.payment_date,
            user=payment.user,
            action_type='payment',
            description=f"{payment.user.name} paid {payment.amount} for {payment.payment_type}."
        ))

    
    recent_appts = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    for appt in recent_appts:
        recent_activities.append(Activity(
            timestamp=appt.created_at,
            user=appt.patient,
            action_type='appointment',
            description=f"{appt.patient.name} booked with Dr. {appt.doctor.name} ({appt.status})."
        ))

    
    recent_activities.sort(key=lambda x: x.timestamp, reverse=True)

    
    recent_activities = recent_activities[:10]

    return render_template('admin/reports.html',
        total_users=total_users,
        new_users_this_month=new_users_this_month,
        total_appointments=total_appointments,
        completed_appointments=completed_appointments,
        total_revenue=round(total_revenue, 2),
        monthly_revenue=round(monthly_revenue, 2),
        active_subscriptions=active_subscriptions,
        subscription_conversion=subscription_conversion,

        doctor_count=doctor_count,
        patient_count=patient_count,
        admin_count=admin_count,

        pending_appointments=pending_appointments,
        confirmed_appointments=confirmed_appointments,
        cancelled_appointments=cancelled_appointments,

        user_registration_labels=user_registration_labels,
        user_registration_data=user_registration_data,

        revenue_labels=revenue_labels,
        revenue_data=revenue_data,

        top_doctors=top_doctors,
        recent_activities=recent_activities,

        database_health=database_health,
        file_storage_usage=file_storage_usage,
        email_delivery_rate=email_delivery_rate,
        api_uptime=api_uptime
    )

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_database_size():
    try:
        db_path = os.path.join(os.path.dirname(current_app.root_path), 'instance', 'healnex.db')
        total_bytes = os.path.getsize(db_path)
        return format_bytes(total_bytes)
    except Exception as e:
        return f"Error: {str(e)}"

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    form = SystemSettingsForm()

    if form.validate_on_submit():

        Setting.set('platform_name', form.site_name.data)
        Setting.set('admin_email', form.admin_email.data)
        Setting.set('max_file_size', str(form.max_file_size.data))
        Setting.set('session_timeout', str(form.session_timeout.data))
        Setting.set('maintenance_mode', 'on' if form.maintenance_mode.data else '')
        Setting.set('new_registrations', 'on' if form.registration_enabled.data else '')
        Setting.set('smtp_server', form.smtp_server.data)
        Setting.set('smtp_port', str(form.smtp_port.data))
        Setting.set('email_notifications', 'on' if form.email_notifications.data else '')

        flash('System settings updated successfully!', 'success')
        return redirect(url_for('admin.system_settings'))

    
    settings = {
        'platform_name': Setting.get('platform_name', 'HealneX'),
        'admin_email': Setting.get('admin_email', 'help@healnex.in'),
        'max_file_size': float(Setting.get('max_file_size', 16)),
        'session_timeout': int(Setting.get('session_timeout', 60)),
        'maintenance_mode': Setting.get('maintenance_mode', '') == 'on',
        'new_registrations': Setting.get('new_registrations', '') == 'on',
        'smtp_server': Setting.get('smtp_server', 'localhost'),
        'smtp_port': int(Setting.get('smtp_port', 587)),
        'email_notifications': Setting.get('email_notifications', '') == 'on'
    }

    
    form.site_name.data = settings['platform_name']
    form.admin_email.data = settings['admin_email']
    form.max_file_size.data = settings['max_file_size']
    form.session_timeout.data = settings['session_timeout']
    form.maintenance_mode.data = settings['maintenance_mode']
    form.registration_enabled.data = settings['new_registrations']
    form.smtp_server.data = settings['smtp_server']
    form.smtp_port.data = settings['smtp_port']
    form.email_notifications.data = settings['email_notifications']

    return render_template('admin/system_settings.html', form=form, settings=settings,db_size=get_database_size(), total_users=User.query.count(), total_appointments=Appointment.query.count())
