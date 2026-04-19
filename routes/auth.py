from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from . import auth_bp


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('notes.notes_index'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password2 = request.form['password2']

        if not username or not email or not password:
            flash('Все поля обязательны.')
            return render_template('register.html')

        if password != password2:
            flash('Пароли не совпадают.')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Логин уже занят.')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован.')
            return render_template('register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна. Войдите в систему.')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('notes.notes_index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Вы вошли в систему.')
            return redirect(url_for('notes.notes_index'))
        else:
            flash('Неверный логин или пароль.')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.')
    return redirect(url_for('index'))