
import os
from flask.cli import FlaskGroup
from app import create_app, db
from app.models import User, Appointment, Payment, MedicalFile, Message, Notification, Referral, DoctorReferral

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
cli = FlaskGroup(app)

@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Appointment=Appointment, Payment=Payment,
                MedicalFile=MedicalFile, Message=Message, Notification=Notification,
                Referral=Referral, DoctorReferral=DoctorReferral)
 
@app.cli.command()
def init_db():
    
    db.create_all()

@app.cli.command()
def seed_db():
    
    from seed_data import seed_database
    seed_database()

if __name__ == '__main__':
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
