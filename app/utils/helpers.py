import os
import secrets
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timedelta

def save_picture(form_picture, folder_name, size=(800, 800)):
    
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    
    
    folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(folder_path, exist_ok=True)
    
    picture_path = os.path.join(folder_path, picture_fn)
    
    
    if f_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
        img = Image.open(form_picture)
        img.thumbnail(size)
        img.save(picture_path)
    else:
        
        form_picture.save(picture_path)
    
    return picture_fn

def allowed_file(filename):
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_file_size(file_path):
    
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def format_file_size(size_bytes):
    
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

def generate_unique_filename(original_filename):
    
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
    return unique_name

def is_doctor_available(doctor, appointment_date, appointment_time):
    
    from app.models import Appointment
    
    
    if not (doctor.working_hours_start <= appointment_time <= doctor.working_hours_end):
        return False
    
    
    existing_appointment = Appointment.query.filter_by(
        doctor_id=doctor.id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status='confirmed'
    ).first()
    
    return existing_appointment is None

def calculate_age(birth_date):
    
    today = datetime.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def get_available_time_slots(doctor, date):
    
    from app.models import Appointment

    
    if not doctor.working_hours_start or not doctor.working_hours_end:
        return []

    start_time = datetime.combine(date, doctor.working_hours_start)
    end_time = datetime.combine(date, doctor.working_hours_end)

    if end_time <= start_time:
        end_time += timedelta(days=1)

    
    booked_times = set(
        appt.appointment_time.strftime('%H:%M')
        for appt in Appointment.query.filter_by(
            doctor_id=doctor.id,
            appointment_date=date,
            status='confirmed'
        ).all()
    )

    
    slots = []
    current_time = start_time
    while current_time + timedelta(minutes=30) <= end_time:
        time_str = current_time.strftime('%H:%M')
        if time_str not in booked_times:
            slots.append(current_time.time())
        current_time += timedelta(minutes=30)

    return slots

def create_notification(user_id, title, message, notification_type, link=None):
    
    from app.models import Notification
    from app import db
    
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

def paginate_query(query, page, per_page=10):
    
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
