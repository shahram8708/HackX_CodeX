from app import db
from app.models import Notification
from datetime import datetime
from datetime import timedelta

def create_notification(user_id, title, message, notification_type, link=None):
    
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
    
    db.session.add(notification)
    db.session.commit()
    return notification

def mark_notification_read(notification_id, user_id):
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user_id
    ).first()
    
    if notification:
        notification.is_read = True
        db.session.commit()
        return True
    return False

def mark_all_notifications_read(user_id):
    
    notifications = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).all()
    
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    return len(notifications)

def get_unread_count(user_id):
    
    return Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()

def delete_old_notifications(days=30):
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    old_notifications = Notification.query.filter(
        Notification.created_at < cutoff_date,
        Notification.is_read == True
    ).all()
    
    for notification in old_notifications:
        db.session.delete(notification)
    
    db.session.commit()
    return len(old_notifications)
