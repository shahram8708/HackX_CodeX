from flask import render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_wtf.csrf import generate_csrf
from flask_login import login_required, current_user
from app import db
from app.notifications import bp
from app.models import Notification
from app.notifications.utils import mark_notification_read, mark_all_notifications_read, get_unread_count
from datetime import datetime, timedelta

@bp.route('/')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    
    filter_type = request.args.get('filter', 'all')
    
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)
    elif filter_type != 'all':
        
        query = query.filter_by(notification_type=filter_type)
    
    notifications = query.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    
    type_counts = db.session.query(
        Notification.notification_type,
        db.func.count(Notification.id)
    ).filter_by(user_id=current_user.id).group_by(
        Notification.notification_type
    ).all()
    
    unread_count = get_unread_count(current_user.id)
    
    response = make_response(render_template(
        'notifications/notifications.html',
        notifications=notifications,
        type_counts=type_counts,
        unread_count=unread_count,
        current_filter=filter_type
    ))
    
    
    response.set_cookie('csrf_token', generate_csrf())
    return response

@bp.route('/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_read(notification_id):
    success = mark_notification_read(notification_id, current_user.id)
    
    if success:
        if request.is_json:
            return jsonify({'success': True})
        flash('Notification marked as read.', 'success')
    else:
        if request.is_json:
            return jsonify({'error': 'Notification not found'}), 404
        flash('Notification not found.', 'danger')
    
    return redirect(url_for('notifications.notifications'))

@bp.route('/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    count = mark_all_notifications_read(current_user.id)
    
    if request.is_json:
        return jsonify({'success': True, 'count': count})
    
    flash(f'{count} notifications marked as read.', 'success')
    return redirect(url_for('notifications.notifications'))

@bp.route('/delete/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()
    
    if notification:
        db.session.delete(notification)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True})
        flash('Notification deleted.', 'success')
    else:
        if request.is_json:
            return jsonify({'error': 'Notification not found'}), 404
        flash('Notification not found.', 'danger')
    
    return redirect(url_for('notifications.notifications'))

@bp.route('/view/<int:notification_id>')
@login_required
def view_notification(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()
    
    
    if not notification.is_read:
        notification.is_read = True
        db.session.commit()
    
    
    if notification.link:
        return redirect(notification.link)
    
    
    return render_template('notifications/notification_detail.html', 
                         notification=notification)

@bp.route('/api/unread_count')
@login_required
def api_unread_count():
    
    count = get_unread_count(current_user.id)
    return jsonify({'unread_count': count})

@bp.route('/api/recent')
@login_required
def api_recent_notifications():
    
    limit = request.args.get('limit', 5, type=int)
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(limit).all()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
        'link': n.link
    } for n in notifications])

@bp.route('/clear_all', methods=['POST'])
@login_required
def clear_all_notifications():
    
    deleted_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=True
    ).delete()
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'deleted_count': deleted_count})
    
    flash(f'{deleted_count} notifications cleared.', 'success')
    return redirect(url_for('notifications.notifications'))


@bp.app_context_processor
def inject_notification_count():
    if current_user.is_authenticated:
        unread_count = get_unread_count(current_user.id)
        return {'unread_notification_count': unread_count}
    return {'unread_notification_count': 0}
