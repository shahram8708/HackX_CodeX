from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import config
import os
from flask_migrate import Migrate

migrate = Migrate()

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name=None):
    app = Flask(__name__)
    migrate.init_app(app, db)
    
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    app.config.from_object(config[config_name])
    
    
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    
    from app import models
    
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    from app.appointments import bp as appointments_bp
    app.register_blueprint(appointments_bp, url_prefix='/appointments')
    
    from app.uploads import bp as uploads_bp
    app.register_blueprint(uploads_bp, url_prefix='/uploads')
    
    from app.chat import bp as chat_bp
    app.register_blueprint(chat_bp, url_prefix='/chat')
    
    from app.payments import bp as payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')
    
    from app.referrals import bp as referrals_bp
    app.register_blueprint(referrals_bp, url_prefix='/referrals')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    from app.ai_assistant import bp as ai_assistant_bp
    app.register_blueprint(ai_assistant_bp, url_prefix='/ai-assistant')

    from app.ai_automation import bp as ai_automation_bp
    app.register_blueprint(ai_automation_bp, url_prefix='/ai-automation')
    
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    from app.auth.forms import LoginForm  

    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role == 'patient':
                return redirect(url_for('dashboard.patient_dashboard'))
            elif current_user.role == 'doctor':
                return redirect(url_for('dashboard.doctor_dashboard'))
            elif current_user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
        return render_template('home.html')
    
    @app.route('/home')
    def home():
        return render_template('home.html')
    
    @app.route('/about')
    def about():
        return render_template('about.html')
    
    @app.route('/terms')
    def terms():
        return render_template('terms_of_service.html')
    
    @app.route('/policy')
    def policy():
        return render_template('privacy_policy.html')
    
    @app.route('/features')
    def features():
        return render_template('features.html')

    
    with app.app_context():
        db.create_all()
    
    return app

