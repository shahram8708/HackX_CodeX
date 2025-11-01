from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.referrals import bp
from app.referrals.forms import DoctorReferralForm, ReferralResponseForm
from app.models import User, DoctorReferral, Referral, Notification
from app.utils.decorators import patient_required
from app.utils.helpers import create_notification
from app.utils.email import send_referral_notification
from datetime import datetime

@bp.route('/patient')
@login_required
@patient_required
def patient_referrals():
    
    referrals_made = Referral.query.filter_by(referrer_id=current_user.id).all()
    total_points = sum(ref.points_awarded for ref in referrals_made)
    
    
    doctor_referrals = DoctorReferral.query.filter_by(patient_id=current_user.id).all()

    referral_points = total_points
    total_referrals = len(referrals_made)
    reward_value = referral_points * 0.1
    referrals = Referral.query.filter_by(referrer_id=current_user.id).all()
    top_referrers = db.session.query(
        User.name,
        db.func.count(Referral.id).label('total_referrals')
    ).join(Referral, Referral.referrer_id == User.id).group_by(User.id).order_by(
        db.func.count(Referral.id).desc()
    ).limit(5).all()
    return render_template('referrals/referral_patient.html',
                         referrals_made=referrals_made,
                         total_points=total_points,
                         doctor_referrals=doctor_referrals,
                         referral_code=current_user.referral_code,
                         referral_points=referral_points,
                         total_referrals=total_referrals,
                         reward_value=reward_value,
                         referrals=referrals,
                         top_referrers=top_referrers)

@bp.route('/share')
@login_required
@patient_required
def share_referral_code():
    
    return render_template('referrals/share_code.html', 
                         referral_code=current_user.referral_code)

@bp.route('/api/referral_stats')
@login_required
def referral_stats():
    
    if current_user.role == 'patient':
        
        total_referrals = Referral.query.filter_by(referrer_id=current_user.id).count()
        total_points = db.session.query(db.func.sum(Referral.points_awarded)).filter_by(
            referrer_id=current_user.id
        ).scalar() or 0
        
        doctor_referrals = DoctorReferral.query.filter_by(patient_id=current_user.id).count()
        
        return jsonify({
            'total_referrals': total_referrals,
            'total_points': total_points,
            'doctor_referrals': doctor_referrals,
            'referral_code': current_user.referral_code
        })
    
    elif current_user.role == 'doctor':
        
        sent_referrals = DoctorReferral.query.filter_by(from_doctor_id=current_user.id).count()
        received_referrals = DoctorReferral.query.filter_by(to_doctor_id=current_user.id).count()
        pending_received = DoctorReferral.query.filter_by(
            to_doctor_id=current_user.id,
            status='pending'
        ).count()
        
        return jsonify({
            'sent_referrals': sent_referrals,
            'received_referrals': received_referrals,
            'pending_received': pending_received
        })
    
    return jsonify({})

@bp.route('/history')
@login_required
def referral_history():
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    if current_user.role == 'patient':
        
        referrals = Referral.query.filter_by(
            referrer_id=current_user.id
        ).order_by(Referral.date_referred.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        doctor_referrals = DoctorReferral.query.filter_by(
            patient_id=current_user.id
        ).order_by(DoctorReferral.referral_date.desc()).all()

        total_referrals = referrals.total
        total_points = sum(ref.points_awarded or 0 for ref in referrals.items)
        rewards_count = total_points // 100

        return render_template('referrals/patient_history.html',
                            referrals=referrals,
                            doctor_referrals=doctor_referrals,
                            total_referrals=total_referrals,
                            total_points=total_points,
                            rewards_count=rewards_count)

    return redirect(url_for('dashboard.patient_dashboard' if current_user.role == 'patient' else 'dashboard.doctor_dashboard'))
