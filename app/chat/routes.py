from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.chat import bp
from app.models import User, Message, Appointment
from app.utils.decorators import verified_required
from app.utils.helpers import create_notification
from datetime import datetime
from flask_wtf.csrf import generate_csrf
from flask import make_response

@bp.route('/')
@login_required
@verified_required
def chat_index():
    
    if current_user.role == 'patient':
        doctor_ids = [id[0] for id in db.session.query(Appointment.doctor_id).filter(
            Appointment.patient_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed'])
        ).distinct()]

        contacts = User.query.filter(
            User.id.in_(doctor_ids),
            User.role == 'doctor'
        ).all()
        
    elif current_user.role == 'doctor':
        patient_ids = [id[0] for id in db.session.query(Appointment.patient_id).filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed'])
        ).distinct()]
     
        contacts = User.query.filter(
            User.id.in_(patient_ids),
            User.role == 'patient'
        ).all()
    
    else:
        contacts = []
    
    
    contact_data = []
    for contact in contacts:
        unread_count = Message.query.filter_by(
            sender_id=contact.id,
            receiver_id=current_user.id,
            is_read=False
        ).count()
        
        
        last_message = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == contact.id)) |
            ((Message.sender_id == contact.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        
        contact_data.append({
            'user': contact,
            'unread_count': unread_count,
            'last_message': last_message
        })
    
    
    contact_data.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
    
    return render_template('chat/chat.html', contacts=contact_data, selected_user=None)

@bp.route('/with/<int:user_id>')
@login_required
@verified_required
def chat_with_user(user_id):
    
    contact = User.query.get_or_404(user_id)
    
    
    if current_user.role == 'patient' and contact.role == 'doctor':
        relationship = Appointment.query.filter_by(
            patient_id=current_user.id,
            doctor_id=contact.id
        ).first()
    elif current_user.role == 'doctor' and contact.role == 'patient':
        relationship = Appointment.query.filter_by(
            patient_id=contact.id,
            doctor_id=current_user.id
        ).first()
    else:
        relationship = None
    
    if not relationship:
        flash('You can only chat with your doctors/patients.', 'warning')
        return redirect(url_for('chat.chat_index'))
    
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == contact.id)) |
        ((Message.sender_id == contact.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    
    unread_messages = Message.query.filter_by(
        sender_id=contact.id,
        receiver_id=current_user.id,
        is_read=False
    ).all()
    
    for message in unread_messages:
        message.is_read = True

    
    if current_user.role == 'patient':
        ids = [id[0] for id in db.session.query(Appointment.doctor_id).filter(
            Appointment.patient_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed'])
        ).distinct()]
        contacts = User.query.filter(User.id.in_(ids), User.role == 'doctor').all()
    elif current_user.role == 'doctor':
        ids = [id[0] for id in db.session.query(Appointment.patient_id).filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status.in_(['pending', 'confirmed'])
        ).distinct()]
        contacts = User.query.filter(User.id.in_(ids), User.role == 'patient').all()
    else:
        contacts = []

    contact_data = []
    for c in contacts:
        unread = Message.query.filter_by(sender_id=c.id, receiver_id=current_user.id, is_read=False).count()
        last = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == c.id)) |
            ((Message.sender_id == c.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        contact_data.append({'user': c, 'unread_count': unread, 'last_message': last})
    contact_data.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
        
    db.session.commit()
    
    response = make_response(render_template(
        'chat/chat.html',
        messages=messages,
        selected_user=contact,
        contacts=contact_data,
        current_user_id=current_user.id
    ))
    response.set_cookie('csrf_token', generate_csrf())
    return response

@bp.route('/api/send_message', methods=['POST'])
@login_required
@verified_required
def send_message():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    
    if not receiver_id or not content:
        return jsonify({'error': 'Missing receiver_id or content'}), 400
    
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404
    
    
    if current_user.role == 'patient' and receiver.role == 'doctor':
        relationship = Appointment.query.filter_by(
            patient_id=current_user.id,
            doctor_id=receiver.id
        ).first()
    elif current_user.role == 'doctor' and receiver.role == 'patient':
        relationship = Appointment.query.filter_by(
            patient_id=receiver.id,
            doctor_id=current_user.id
        ).first()
    else:
        relationship = None
    
    if not relationship:
        return jsonify({'error': 'Cannot send message to this user'}), 403
    
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content
    )
    
    db.session.add(message)
    db.session.commit()
    
    
    create_notification(
        receiver_id,
        'New Message',
        f'New message from {current_user.name}',
        'message',
        url_for('chat.chat_with_user', user_id=current_user.id)
    )
    
    return jsonify({
        'success': True,
        'message': message.to_dict()
    })

@bp.route('/api/messages/<int:user_id>')
@login_required
@verified_required
def get_messages(user_id):
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    return jsonify([message.to_dict() for message in messages])

@bp.route('/api/mark_read/<int:sender_id>', methods=['POST'])
@login_required
def mark_messages_read(sender_id):
    
    messages = Message.query.filter_by(
        sender_id=sender_id,
        receiver_id=current_user.id,
        is_read=False
    ).all()
    
    for message in messages:
        message.is_read = True
    
    db.session.commit()
    
    return jsonify({'success': True, 'marked_count': len(messages)})



from flask import jsonify, current_app
from sqlalchemy import func
active_video_rooms = {} 

from sqlalchemy import func, or_

@bp.route('/video/start/<int:patient_id>', methods=['POST'])
@login_required
def start_video_call(patient_id):
    from sqlalchemy import func

    if current_user.role != 'doctor':
        return jsonify({'error': 'Only doctors can start a call'}), 403

    appointment = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.patient_id == patient_id,
        func.lower(func.trim(Appointment.status)).in_(['pending', 'confirmed'])
    ).first()

    if not appointment:
        return jsonify({'error': 'No appointment found with this patient'}), 400

    
    room_name = f"healthconnect_d{current_user.id}_p{patient_id}"
    active_video_rooms[(current_user.id, patient_id)] = {
        'room_name': room_name,
        'started_at': datetime.utcnow()
    }
    
    call_message = Message(
        sender_id=current_user.id,
        receiver_id=patient_id,
        content="📞 Doctor has started a video call."
    )
    db.session.add(call_message)
    db.session.commit()

    
    create_notification(
        patient_id,
        'Video Call',
        f'{current_user.name} has started a video call.',
        'video_call',
        url_for('chat.chat_with_user', user_id=current_user.id)
    )

    return jsonify({'room_name': room_name})

from datetime import datetime, timedelta

@bp.route('/video/join/<int:doctor_id>', methods=['GET'])
@login_required
def join_video_call(doctor_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Only patients can join a call'}), 403

    
    appointment = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.patient_id == current_user.id,
        func.lower(func.trim(Appointment.status)).in_(['pending', 'confirmed'])
    ).first()

    if not appointment:
        return jsonify({'error': 'No appointment found with this doctor'}), 403

    room_data = active_video_rooms.get((doctor_id, current_user.id))

    if not room_data:
        return jsonify({'error': 'Doctor has not started the call yet'}), 404

    
    if datetime.utcnow() - room_data['started_at'] > timedelta(minutes=3):
        
        active_video_rooms.pop((doctor_id, current_user.id), None)
        return jsonify({'error': 'Video call session has expired.'}), 410

    return jsonify({'room_name': room_data['room_name']})

@bp.route('/api/delete_conversation/<int:user_id>', methods=['DELETE'])
@login_required
@verified_required
def delete_conversation(user_id):
    
    if current_user.role == 'patient':
        appointment = Appointment.query.filter_by(
            patient_id=current_user.id,
            doctor_id=user_id
        ).first()
    elif current_user.role == 'doctor':
        appointment = Appointment.query.filter_by(
            patient_id=user_id,
            doctor_id=current_user.id
        ).first()
    else:
        appointment = None

    if not appointment:
        return jsonify({'error': 'No valid relationship found'}), 403

    
    Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).delete()
    db.session.commit()

    return jsonify({'success': True, 'message': 'Conversation deleted'})

@bp.route('/api/chat_stats')
@login_required
def chat_stats():
    
    unread_count = Message.query.filter_by(
        receiver_id=current_user.id,
        is_read=False
    ).count()
    
    
    if current_user.role == 'patient':
        total_conversations = db.session.query(Appointment.doctor_id).filter_by(
            patient_id=current_user.id
        ).distinct().count()
    elif current_user.role == 'doctor':
        total_conversations = db.session.query(Appointment.patient_id).filter_by(
            doctor_id=current_user.id
        ).distinct().count()
    else:
        total_conversations = 0
    
    return jsonify({
        'unread_count': unread_count,
        'total_conversations': total_conversations
    })
