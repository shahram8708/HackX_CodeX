from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.appointments import bp
from app.appointments.forms import BookAppointmentForm, RescheduleAppointmentForm, SearchDoctorsForm
from app.models import User, Appointment, Payment
from app.utils.decorators import patient_required, doctor_required
from app.utils.helpers import get_available_time_slots, create_notification
from app.utils.email import send_appointment_confirmation
import stripe
from flask import current_app
from datetime import datetime, timedelta, time, date

def generate_time_slots(start_time, end_time, interval_minutes=30):
    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end = datetime.combine(datetime.today(), end_time)

    while current <= end:
        slots.append(current.strftime('%H:%M'))
        current += timedelta(minutes=interval_minutes)
    return slots

@bp.route('/book')
@login_required
@patient_required
def book_appointment():
    
    search_form = SearchDoctorsForm()
    
    
    specializations = db.session.query(User.specialization).filter_by(role='doctor').distinct().all()
    search_form.specialization.choices += [(spec[0], spec[0]) for spec in specializations if spec[0]]
    
    
    doctors_query = User.query.filter_by(role='doctor', is_active=True)
    
    if request.args.get('specialization'):
        doctors_query = doctors_query.filter(User.specialization == request.args.get('specialization'))

    if request.args.get('search'):
        search_term = request.args.get('search')
        doctors_query = doctors_query.filter(
            (User.name.ilike(f"%{search_term}%")) |
            (User.specialization.ilike(f"%{search_term}%"))
        )

    page = request.args.get('page', 1, type=int)
    per_page = 6  

    doctors = doctors_query.paginate(page=page, per_page=per_page)

    booking_form = BookAppointmentForm()
    return render_template('appointments/book_appointment.html', 
                         doctors=doctors, 
                         search_form=search_form, 
                         booking_form=booking_form)

@bp.route('/book/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def book_appointment_with_doctor(doctor_id):
    doctor = User.query.filter_by(id=doctor_id, role='doctor').first_or_404()
    form = BookAppointmentForm()
    form.doctor_id.data = doctor_id
    payment_method = form.payment_method.data 
    
    if form.validate_on_submit():
        
        existing_appointment = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=form.appointment_date.data,
            appointment_time=datetime.strptime(form.appointment_time.data, '%H:%M').time(),
            status='confirmed'
        ).first()
        
        if existing_appointment:
            flash('This time slot is no longer available. Please choose another time.', 'warning')
            return redirect(url_for('appointments.book_appointment_with_doctor', doctor_id=doctor_id))
        
        
        from sqlalchemy import extract

        now = datetime.utcnow()
        subscription_tier = current_user.subscription_tier or 'free'
        subscription_cycle = current_user.subscription_plan or 'monthly'

        if subscription_cycle == 'monthly':
            date_start = datetime(now.year, now.month, 1)
        elif subscription_cycle == 'annual':
            date_start = datetime(now.year, 1, 1)
        else:
            date_start = datetime(now.year, now.month, 1)

        appointments_count = Appointment.query.filter(
            Appointment.patient_id == current_user.id,
            Appointment.appointment_date >= date_start,
            Appointment.status.in_(['pending', 'confirmed', 'completed'])
        ).count()

        if subscription_tier == 'basic':
            max_allowed = 3
        elif subscription_tier == 'premium':
            max_allowed = float('inf')  
        elif subscription_tier == 'enterprise':
            max_allowed = float('inf')  
        else:
            max_allowed = 1

        
        if appointments_count >= max_allowed:
            flash('You have reached your monthly appointment limit for your current subscription plan.', 'warning')
            return redirect(url_for('appointments.my_appointments'))

        
        if current_user.subscription_tier and current_user.subscription_tier != 'free':
            if (not current_user.subscription_active or
                not current_user.subscription_expiry or
                current_user.subscription_expiry < datetime.utcnow()):
                flash("Your subscription has expired. Please renew to book an appointment.", "danger")
                return redirect(url_for('payments.subscription_plans'))

        
        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            appointment_type=form.appointment_type.data,
            appointment_date=form.appointment_date.data,
            appointment_time=datetime.strptime(form.appointment_time.data, '%H:%M').time(),
            notes=form.notes.data,
            reason=form.reason.data,
            payment_method=payment_method,
            status='pending'  
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        
        if form.appointment_type.data == 'teleconsultation' or payment_method == 'online':
            if doctor.consultation_fee and doctor.consultation_fee > 0:
                return redirect(url_for('payments.checkout_appointment', appointment_id=appointment.id))
            else:
                appointment.status = 'confirmed'
                db.session.commit()
                send_appointment_confirmation(appointment)
                create_notification(current_user.id, 'Appointment Confirmed',
                                    f'Your appointment with Dr. {doctor.name} has been confirmed.', 'appointment')
                create_notification(doctor.id, 'New Appointment',
                                    f'New appointment booked by {current_user.name}.', 'appointment')
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('appointments.my_appointments'))

        
        appointment.status = 'pending'
        appointment.notes = (appointment.notes or '') + '\n(Patient will pay offline at the clinic/hospital)'
        db.session.commit()

        send_appointment_confirmation(appointment)
        create_notification(current_user.id, 'Appointment Pending Payment',
                            f'Your appointment with Dr. {doctor.name} is booked and pending offline payment.', 'appointment')
        create_notification(doctor.id, 'New Appointment (Offline Payment)',
                            f'New appointment booked by {current_user.name}. Payment will be made offline.', 'appointment')

        flash('Appointment booked successfully. Please pay at the clinic/hospital.', 'info')
        return redirect(url_for('appointments.my_appointments'))

    return render_template('appointments/book_with_doctor.html', form=form, doctor=doctor)

@bp.route('/api/available_times/<int:doctor_id>/<date>')
@login_required
def get_available_times(doctor_id, date):
    
    try:
        appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
        doctor = User.query.get_or_404(doctor_id)
        
        
        if appointment_date < datetime.now().date():
            return jsonify({'times': []})
        
        
        available_times = get_available_time_slots(doctor, appointment_date)
        
        
        time_choices = [(t.strftime('%H:%M'), t.strftime('%I:%M %p')) for t in available_times]
        
        return jsonify({'times': time_choices})
    
    except Exception as e:
        return jsonify({'error': str(e)})

@bp.route('/my_appointments')
@login_required
def my_appointments():
    today = datetime.today().date()

    if current_user.role == 'patient':
        upcoming_appointments = Appointment.query.filter(
            Appointment.patient_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed']),
            Appointment.appointment_date >= today
        ).order_by(Appointment.appointment_date.asc()).all()

        completed_appointments = Appointment.query.filter_by(
            patient_id=current_user.id,
            status='completed'
        ).order_by(Appointment.appointment_date.desc()).all()

        cancelled_appointments = Appointment.query.filter_by(
            patient_id=current_user.id,
            status='cancelled'
        ).order_by(Appointment.appointment_date.desc()).all()

    elif current_user.role == 'doctor':
        upcoming_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed']),
            Appointment.appointment_date >= today
        ).order_by(Appointment.appointment_date.asc()).all()

        completed_appointments = Appointment.query.filter_by(
            doctor_id=current_user.id,
            status='completed'
        ).order_by(Appointment.appointment_date.desc()).all()

        cancelled_appointments = Appointment.query.filter_by(
            doctor_id=current_user.id,
            status='cancelled'
        ).order_by(Appointment.appointment_date.desc()).all()

    else:
        
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))

    return render_template(
        'appointments/appointments_list.html',
        upcoming_appointments=upcoming_appointments,
        completed_appointments=completed_appointments,
        cancelled_appointments=cancelled_appointments
    )

@bp.route('/appointment/<int:appointment_id>')
@login_required
def view_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    
    if current_user.role == 'patient' and appointment.patient_id != current_user.id:
        flash('You do not have permission to view this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))
    
    if current_user.role == 'doctor' and appointment.doctor_id != current_user.id:
        flash('You do not have permission to view this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))
    
    return render_template('appointments/appointment_detail.html', appointment=appointment, today_date=date.today())

@bp.route('/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    
    if current_user.role == 'patient' and appointment.patient_id != current_user.id:
        flash('You do not have permission to cancel this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))
    
    if current_user.role == 'doctor' and appointment.doctor_id != current_user.id:
        flash('You do not have permission to cancel this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))
    
    if appointment.status in ['completed', 'cancelled']:
        flash('This appointment cannot be cancelled.', 'warning')
        return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))
    
    
    payment = Payment.query.filter_by(appointment_id=appointment.id, status='completed').first()

    if payment and payment.stripe_payment_intent_id:
        try:
            
            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id
            )

            
            payment.status = 'refunded'
            appointment.status = 'cancelled'
            appointment.updated_at = datetime.utcnow()

            
            if current_user.role == 'patient':
                create_notification(
                    appointment.doctor_id,
                    'Appointment Cancelled & Refunded',
                    f'Appointment with {current_user.name} was cancelled. Refund processed.',
                    'appointment'
                )
            else:
                create_notification(
                    appointment.patient_id,
                    'Appointment Cancelled & Refunded',
                    f'Your appointment with Dr. {current_user.name} was cancelled and refunded.',
                    'appointment'
                )

            db.session.commit()
            flash('Appointment cancelled and refunded successfully.', 'success')
            return redirect(url_for('appointments.my_appointments'))

        except stripe.error.StripeError as e:
            current_app.logger.error(f'Refund failed: {str(e)}')
            flash('Refund could not be processed. Appointment not cancelled.', 'danger')
            return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))
    else:
        
        appointment.status = 'cancelled'
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Appointment cancelled successfully.', 'info')
        return redirect(url_for('appointments.my_appointments'))

@bp.route('/appointment/<int:appointment_id>/complete', methods=['POST'])
@login_required
@doctor_required
def complete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != current_user.id:
        flash('You do not have permission to modify this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))

    if appointment.status != 'confirmed' and appointment.payment_method != 'offline':
        flash('Only confirmed appointments can be marked as completed.', 'warning')
        return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

    try:
        doctor = appointment.doctor

        if appointment.payment_method == 'online':
            payment = Payment.query.filter_by(appointment_id=appointment.id, status='completed').first()
            if not payment:
                flash('Payment not completed. Cannot mark appointment as completed.', 'warning')
                return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

            
            if not all([
                doctor.stripe_account_id
            ]):
                flash('Doctor payout details are missing or incomplete. Cannot proceed.', 'danger')
                return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

            try:
                payout_percentage = 0.80 
                payout_amount_cents = int(doctor.consultation_fee * payout_percentage * 100)

                
                if not getattr(doctor, 'stripe_account_id', None):
                    flash('Doctor payout not possible. Please complete Stripe onboarding from Edit Profile.', 'warning')
                    return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

                account = stripe.Account.retrieve(doctor.stripe_account_id)
                if not account.capabilities.get('transfers') == 'active':
                    flash('Doctor Stripe account is not fully onboarded for payouts. Please complete onboarding.', 'warning')
                    return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

                
                stripe.Transfer.create(
                    amount=payout_amount_cents,
                    currency='eur',
                    destination=doctor.stripe_account_id,
                    description=f'Consultation payout for appointment #{appointment.id}'
                )

                current_app.logger.info(
                    f"[REAL PAYOUT SUCCESS] {doctor.consultation_fee} transferred to Dr. {doctor.name} (Stripe ID: {doctor.stripe_account_id})"
                )

            except stripe.error.StripeError as e:
                current_app.logger.error(f"Stripe payout failed: {str(e)}")
                flash('Payout to doctor failed. Please try again or contact support.', 'danger')
                return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

        elif appointment.payment_method == 'offline':
            
            current_app.logger.info(f"[OFFLINE COMPLETION] Doctor: {doctor.name}, Appointment ID: {appointment.id}")

        
        appointment.status = 'completed'
        appointment.updated_at = datetime.utcnow()

        create_notification(
            appointment.patient_id,
            'Appointment Completed',
            f'Your appointment with Dr. {doctor.name} has been marked as completed.',
            'appointment'
        )

        db.session.commit()
        flash('Appointment marked as completed successfully.', 'success')
        return redirect(url_for('dashboard.add_treatment', patient_id=appointment.patient.unique_patient_id))

    except Exception as e:
        current_app.logger.error(f"Error completing appointment {appointment_id}: {str(e)}")
        flash('An error occurred while completing the appointment.', 'danger')
        return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

@bp.route('/reschedule/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def reschedule_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    
    if current_user.role == 'patient' and appointment.patient_id != current_user.id:
        flash('You do not have permission to reschedule this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))
    
    if appointment.status in ['completed', 'cancelled']:
        flash('This appointment cannot be rescheduled.', 'warning')
        return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))
    
    form = RescheduleAppointmentForm()
    
    if form.validate_on_submit():
        
        new_time = datetime.strptime(form.appointment_time.data, '%H:%M').time()
        existing_appointment = Appointment.query.filter_by(
            doctor_id=appointment.doctor_id,
            appointment_date=form.appointment_date.data,
            appointment_time=new_time,
            status='confirmed'
        ).filter(Appointment.id != appointment_id).first()
        
        if existing_appointment:
            flash('This time slot is not available. Please choose another time.', 'warning')
        else:
            appointment.appointment_date = form.appointment_date.data
            appointment.appointment_time = new_time
            appointment.reason = form.reason.data
            appointment.updated_at = datetime.utcnow()
            
            
            other_user_id = appointment.doctor_id if current_user.role == 'patient' else appointment.patient_id
            other_user_name = appointment.doctor.name if current_user.role == 'patient' else appointment.patient.name
            
            create_notification(
                other_user_id,
                'Appointment Rescheduled',
                f'Appointment has been rescheduled by {current_user.name}.',
                'appointment'
            )
            
            db.session.commit()
            flash('Appointment rescheduled successfully!', 'success')
            return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))
    
    return render_template('appointments/reschedule.html', form=form, appointment=appointment)
