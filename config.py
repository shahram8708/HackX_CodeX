import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'HealneX6708@'
    SQLALCHEMY_DATABASE_URI = "sqlite:///healnex.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = "multimosaic.help@gmail.com"
    MAIL_PASSWORD = "tbky zudp mpkt gnzv"
    MAIL_DEFAULT_SENDER = "multimosaic.help@gmail.com"
    ADMIN_EMAIL = "multimosaic.help@gmail.com"
    
    
    STRIPE_PUBLISHABLE_KEY = "pk_test_51RexJCBNmZYtrMOKirQ9umUzsYkP5WKHCSgRAAG9d5AvZNN0UR4YrNL12Jz1SJw0d5ff91Uo9ZTSsu7hEX8DEiAi00HPGs1rPZ"
    STRIPE_SECRET_KEY = "sk_test_51RexJCBNmZYtrMOKYoFWpWGUhtX5qzfSW8AmvNnvXZSzrTe4dv3hOPx1P9l8ZKqrNEcAPg3SZJA944H3nNhCGIT100VWKVJnPe"
    
    
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'true').lower() in ['true', 'on', '1']
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('WTF_CSRF_TIME_LIMIT') or 3600)
    
    
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 16 * 1024 * 1024)  
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
    
    
    POSTS_PER_PAGE = 10
    
    
    OTP_EXPIRY_MINUTES = 10

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
