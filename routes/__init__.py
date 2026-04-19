from flask import Blueprint

# создаем шаблоны
auth_bp = Blueprint('auth', __name__)
notes_bp = Blueprint('notes', __name__)
export_bp = Blueprint('export', __name__)

# импортируем маршруты после создания шаблонов
from . import auth, notes, export
