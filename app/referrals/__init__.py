from flask import Blueprint

bp = Blueprint('referrals', __name__)

from app.referrals import routes
