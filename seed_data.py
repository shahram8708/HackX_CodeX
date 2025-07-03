from app import create_app, db
from app.models import User, Appointment, Payment, MedicalFile, Message, Notification, Referral, DoctorReferral
from datetime import datetime, timedelta, time
import random
import os

def seed_database():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        
        admin = User(
            name='HealneX MultiMosaic',
            email='multimosaic.help@gmail.com',
            role='admin',
            phone='+91 9876543210',
            is_verified=True,
            is_active=True
        )
        admin.set_password('healnex6708@')
        db.session.add(admin)
        db.session.commit()
        

if __name__ == '__main__':
    seed_database()
