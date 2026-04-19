import os
from flask import Flask, render_template, send_from_directory, redirect, url_for
from flask_login import LoginManager, current_user
import mimetypes

from config import Config
from models import db, User, Category
from routes import auth_bp, notes_bp, export_bp
from routes.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # инициализация бд
    db.init_app(app)

    # инициализация login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # регистрация шаблонов
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(notes_bp, url_prefix='/notes')
    app.register_blueprint(export_bp, url_prefix='/notes')
    app.register_blueprint(api_bp)

    # главная страница для не авторизованных
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('notes.notes_index'))
        return render_template('index.html')

    # для скачивания файлов
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        uploads_folder = app.config['UPLOAD_FOLDER']
        mime_type, _ = mimetypes.guess_type(filename)
        return send_from_directory(
            uploads_folder,
            filename,
            mimetype=mime_type or 'application/octet-stream'
        )

    return app


if __name__ == '__main__':
    app = create_app()

    # делаем папку для загрузок
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    with app.app_context():
        db.create_all()

        # добавляем категории по умолчанию
        default_categories = ["Работа", "Учёба", "Личное", "Заметки"]
        for name in default_categories:
            if not Category.query.filter_by(name=name).first():
                cat = Category(name=name)
                db.session.add(cat)
        db.session.commit()

    app.run(debug=True)