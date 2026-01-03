from flask import Blueprint

bp = Blueprint('ai_automation', __name__)

from app.ai_automation import routes
