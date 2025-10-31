import stripe
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db, csrf
from app.payments import bp
from app.payments.forms import SubscriptionForm, CheckoutForm
from app.models import User, Appointment, Payment, Referral
from app.utils.decorators import patient_required
from app.utils.helpers import create_notification
from app.utils.email import send_payment_receipt, send_appointment_confirmation
from datetime import datetime, timedelta
import json


def get_stripe_keys():
    return {
        'publishable_key': current_app.config.get('STRIPE_PUBLISHABLE_KEY'),
        'secret_key': current_app.config.get('STRIPE_SECRET_KEY')
    }

@bp.before_app_request
def configure_stripe():
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

@bp.route('/plans')
@login_required
@patient_required
def subscription_plans():
    form = SubscriptionForm()
    
    
    current_subscription = None
    if current_user.subscription_active and current_user.subscription_expiry:
        if current_user.subscription_expiry > datetime.utcnow():
            current_subscription = {
                'plan': current_user.subscription_plan,
                'expiry': current_user.subscription_expiry
            }
    
    return render_template('payments/plans.html', 
                         form=form, 
                         current_subscription=current_subscription,
                         stripe_key=get_stripe_keys()['publishable_key'])

@bp.route('/subscribe', methods=['POST'])
@login_required
@patient_required
def subscribe():
    form = SubscriptionForm()
    
    if form.validate_on_submit():
        plan_type = form.plan_type.data
        plan_name = request.form.get('plan_name', 'basic') 
        
        
        pricing_table = {
            'basic': {'monthly': 99.99, 'annual': 999.99},
            'premium': {'monthly': 299.99, 'annual': 2999.99},
            'enterprise': {'monthly': 999.99, 'annual': 9999.99}
        }

        
        if plan_name not in pricing_table or plan_type not in ['monthly', 'annual']:
            flash("Invalid subscription selection.", "danger")
            return redirect(url_for('payments.subscription_plans'))

        
        amount = pricing_table[plan_name][plan_type]
        plan_duration = plan_type
        duration_months = 1 if plan_type == 'monthly' else 12
        from app.models import Referral  

        referral_points = db.session.query(
            db.func.sum(Referral.points_awarded)
        ).filter_by(referrer_id=current_user.id).scalar() or 0
        discount_applied = False

        if referral_points >= 500 and plan_type == 'monthly':
            amount = round(amount * 0.9, 2)  
            discount_applied = True

        try:
            
            stripe.api_key = get_stripe_keys()['secret_key']
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'INR',
                        'product_data': {
                            'name': f'HealneX {plan_type.title()} Subscription',
                        },
                        'unit_amount': int(amount * 100),  
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=url_for('payments.subscription_success', plan=plan_type, _external=True, plan_name=plan_name, referral_discount_applied='yes' if discount_applied else 'no'),
                cancel_url=url_for('payments.subscription_plans', _external=True),
                metadata={
                    'user_id': current_user.id,
                    'plan_type': plan_type,
                    'plan_name': plan_name,
                    'amount': amount,
                    'referral_discount_applied': 'yes' if discount_applied else 'no'
                }
            )
            
            return redirect(session.url)
            
        except stripe.error.StripeError as e:
            flash(f'Payment error: {str(e)}', 'danger')
            return redirect(url_for('payments.subscription_plans'))
    
    flash('Invalid subscription plan selected.', 'danger')
    return redirect(url_for('payments.subscription_plans'))

@bp.route('/subscription/success')
@login_required
@patient_required
def subscription_success():
    plan = request.args.get('plan')
    plan_name = request.args.get('plan_name', 'basic')
    if plan in ['monthly', 'annual']:
        
        current_user.subscription_plan = plan
        current_user.subscription_tier = plan_name 
        current_user.subscription_active = True
        
        referral_discount_applied = request.args.get('referral_discount_applied') == 'yes'
        if referral_discount_applied:
            referrals = Referral.query.filter_by(referrer_id=current_user.id).order_by(Referral.date_referred).all()
            remaining_to_deduct = 500
            for ref in referrals:
                if not ref.points_awarded:
                    continue
                deduct = min(ref.points_awarded, remaining_to_deduct)
                ref.points_awarded -= deduct
                remaining_to_deduct -= deduct
                if remaining_to_deduct <= 0:
                    break

        
        pricing_table = {
            'basic': {'monthly': 99.99, 'annual': 999.99},
            'premium': {'monthly': 299.99, 'annual': 2999.99},
            'enterprise': {'monthly': 999.99, 'annual': 9999.99}
        }

        
        if plan_name not in pricing_table or plan not in ['monthly', 'annual']:
            flash("Invalid subscription details.", "danger")
            return redirect(url_for('payments.subscription_plans'))

        amount = pricing_table[plan_name][plan]

        if plan == 'monthly':
            current_user.subscription_expiry = datetime.utcnow() + timedelta(days=30)
        else:
            current_user.subscription_expiry = datetime.utcnow() + timedelta(days=365)
        
        
        payment = Payment(
            user_id=current_user.id,
            payment_type='subscription',
            amount=amount,
            currency='INR',
            status='completed',
            plan_name=f'{plan_name.title()} ({plan.title()})',
            plan_duration=plan
        )
        
        db.session.add(payment)
        
        
        create_notification(
            current_user.id,
            'Subscription Activated',
            f'Your {plan} subscription has been activated successfully!',
            'payment'
        )
        
        db.session.commit()
        
        
        send_payment_receipt(payment)
        
        flash(f'Subscription activated successfully! Enjoy your {plan} plan.', 'success')
    
    return redirect(url_for('dashboard.patient_dashboard'))

@bp.route('/checkout/appointment/<int:appointment_id>')
@login_required
@patient_required
def checkout_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient_id != current_user.id:
        flash('You do not have permission to pay for this appointment.', 'danger')
        return redirect(url_for('appointments.my_appointments'))

    if appointment.status != 'pending':
        flash('This appointment has already been processed.', 'info')
        return redirect(url_for('appointments.view_appointment', appointment_id=appointment_id))

    doctor = appointment.doctor
    consultation_fee = doctor.consultation_fee

    form = CheckoutForm()
    form.appointment_id.data = appointment_id

    platform_fee = 2.99
    tax_amount = 1.50

    from app.models import Referral

    referral_points = db.session.query(
        db.func.sum(Referral.points_awarded)
    ).filter_by(referrer_id=current_user.id).scalar() or 0

    discount_applied = False
    if referral_points >= 1000:
        consultation_fee = 0
        discount_applied = True

    
    total_amount = round(consultation_fee + platform_fee + tax_amount, 2)

    return render_template(
        'payments/checkout.html',
        appointment=appointment,
        doctor=doctor,
        amount=consultation_fee,
        platform_fee=platform_fee,
        tax_amount=tax_amount,
        form=form,
        total_amount=total_amount,
        stripe_key=get_stripe_keys()['publishable_key'],
        referral_discount_applied=discount_applied
    )

@bp.route('/process_payment/appointment/<int:appointment_id>', methods=['POST'])
@login_required
@patient_required
@csrf.exempt
def process_appointment_payment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    
    if appointment.patient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if appointment.status != 'pending':
        return jsonify({'error': 'Appointment already processed'}), 400
    
    try:
        
        payment_method_id = request.json.get('payment_method_id')
        
        if not payment_method_id:
            return jsonify({'error': 'Payment method required'}), 400
        
        stripe.api_key = get_stripe_keys()['secret_key']
        platform_fee = 2.99
        tax_amount = 1.50
        total_amount = round(appointment.doctor.consultation_fee + platform_fee + tax_amount, 2)
        referral_discount_applied = request.json.get('referral_discount_applied') == 'true'

        consultation_fee = 0 if referral_discount_applied else appointment.doctor.consultation_fee
        total_amount = round(consultation_fee + platform_fee + tax_amount, 2)
        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),
            currency='INR',
            payment_method=payment_method_id,
            confirm=True,
            automatic_payment_methods={
                'enabled': True,
                'allow_redirects': 'never'
            },
            metadata={
                'appointment_id': appointment_id,
                'patient_id': current_user.id,
                'doctor_id': appointment.doctor_id,
                'referral_discount_applied': 'yes' if referral_discount_applied else 'no'
            }
        )
        
        if intent.status == 'succeeded':
            
            appointment.status = 'confirmed'

            if referral_discount_applied:
                referrals = Referral.query.filter_by(referrer_id=current_user.id).order_by(Referral.date_referred).all()
                remaining_to_deduct = 1000
                for ref in referrals:
                    if not ref.points_awarded:
                        continue
                    deduct = min(ref.points_awarded, remaining_to_deduct)
                    ref.points_awarded -= deduct
                    remaining_to_deduct -= deduct
                    if remaining_to_deduct <= 0:
                        break

            payment = Payment(
                user_id=current_user.id,
                payment_type='consultation',
                amount=total_amount,
                currency='INR',
                status='completed',
                payment_method='card',
                transaction_id=intent.id,
                stripe_payment_intent_id=intent.id,
                appointment_id=appointment_id
            )
            
            db.session.add(payment)
            
            
            create_notification(
                current_user.id,
                'Payment Successful',
                f'Payment of {total_amount} completed for appointment with Dr. {appointment.doctor.name}',
                'payment'
            )
            
            create_notification(
                appointment.doctor_id,
                'New Appointment Confirmed',
                f'Appointment with {current_user.name} has been confirmed with payment.',
                'appointment'
            )
            
            db.session.commit()
            
            
            send_payment_receipt(payment)
            send_appointment_confirmation(appointment)
            
            return jsonify({'success': True, 'payment_intent': intent})
        
        else:
            return jsonify({'error': 'Payment failed', 'payment_intent': intent})
    
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f'Payment processing error: {str(e)}')
        return jsonify({'error': 'Payment processing failed'}), 500

@bp.route('/success')
@login_required
def success_page():
    flash("🎉 Payment successful! Your appointment/subscription is confirmed.", "success")
    return redirect(url_for('dashboard.patient_dashboard'))
 
@bp.route('/history')
@login_required
def payment_history():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    payment_type = request.args.get('payment_type')
    date_range = request.args.get('date_range')

    if current_user.role == 'doctor':
        query = Payment.query.join(Appointment).filter(Appointment.doctor_id == current_user.id)
    else:
        query = Payment.query.filter_by(user_id=current_user.id)

    if payment_type in ['consultation', 'subscription']:
        query = query.filter_by(payment_type=payment_type)

    if date_range == 'last_month':
        start_date = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Payment.payment_date >= start_date)
    elif date_range == 'last_3_months':
        start_date = datetime.utcnow() - timedelta(days=90)
        query = query.filter(Payment.payment_date >= start_date)
    elif date_range == 'last_year':
        start_date = datetime.utcnow() - timedelta(days=365)
        query = query.filter(Payment.payment_date >= start_date)

    payments = query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    
    if current_user.role == 'doctor':
        payout_percentage = 0.80
        total_earned = (
            db.session.query(db.func.sum(User.consultation_fee * payout_percentage))
            .join(Appointment, Appointment.doctor_id == User.id)
            .filter(
                Appointment.doctor_id == current_user.id,
                Appointment.status == 'completed'
            ).scalar()
        ) or 0

        consultation_payments = Appointment.query.filter_by(
            doctor_id=current_user.id,
            status='completed'
        ).all()

        subscription_payments = []  

        next_billing_date = None  
    else:
        total_earned = None
        total_spent = db.session.query(db.func.sum(Payment.amount)).filter_by(
            user_id=current_user.id,
            status='completed'
        ).scalar() or 0

        all_payments = Payment.query.filter_by(user_id=current_user.id)
        consultation_payments = all_payments.filter(Payment.payment_type == 'consultation').all()
        subscription_payments = all_payments.filter(Payment.payment_type == 'subscription').all()
        next_billing_date = current_user.subscription_expiry

    return render_template(
        'payments/payment_history.html',
        payments=payments,
        total_spent=total_spent if current_user.role != 'doctor' else None,
        total_earned=total_earned if current_user.role == 'doctor' else None,
        consultation_payments=consultation_payments,
        subscription_payments=subscription_payments,
        next_billing_date=next_billing_date
    )

@bp.route('/receipt/<int:payment_id>')
@login_required
def view_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.user_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to view this receipt.', 'danger')
        return redirect(url_for('payments.payment_history'))
    
    return render_template('payments/receipt.html', payment=payment)

@bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        
        
        
        
        current_app.logger.info(f'Received Stripe webhook: {request.get_json()}')
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        current_app.logger.error(f'Webhook error: {str(e)}')
        return jsonify({'error': str(e)}), 400

@bp.route('/api/payment_stats')
@login_required
def payment_stats():
    
    total_payments = Payment.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).count()
    
    total_spent = db.session.query(db.func.sum(Payment.amount)).filter_by(
        user_id=current_user.id,
        status='completed'
    ).scalar() or 0
    
    this_month_start = datetime.now().replace(day=1)
    this_month_spent = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.user_id == current_user.id,
        Payment.status == 'completed',
        Payment.payment_date >= this_month_start
    ).scalar() or 0
    
    return jsonify({
        'total_payments': total_payments,
        'total_spent': float(total_spent),
        'this_month_spent': float(this_month_spent),
        'subscription_active': current_user.subscription_active
    })
