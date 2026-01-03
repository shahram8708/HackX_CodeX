from flask import Blueprint

bp = Blueprint('ai_assistant', __name__)

from app.ai_assistant import routes
