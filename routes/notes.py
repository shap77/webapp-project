import os
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, Note, Category, Attachment
from utils import allowed_file
from . import notes_bp


@notes_bp.route('/')
@login_required
def notes_index():
    search = request.args.get('search', '')
    category_id = request.args.get('category_id', '')
    only_favorites = request.args.get('favorites', '0')

    user_id = current_user.id
    query = Note.query.filter(Note.user_id == user_id)

    if search:
        query = query.filter(
            (Note.title.contains(search)) | (Note.content.contains(search))
        )

    if category_id:
        try:
            cat_id = int(category_id)
            if cat_id > 0:
                query = query.filter(Note.category_id == cat_id)
        except (ValueError, TypeError):
            pass

    if only_favorites == '1':
        query = query.filter(Note.is_favorite.is_(True))

    notes = query.all()
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        'index.html',
        notes=notes,
        search=search,
        categories=categories,
        selected_category=category_id,
        only_favorites=only_favorites,
    )


@notes_bp.route('/create', methods=['GET', 'POST'])
@login_required
def notes_create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form.get('content', '')
        category_id = request.form.get('category_id')
        is_favorite = bool(request.form.get('is_favorite', False))
        file = request.files.get('file')

        if not title:
            flash('Заголовок обязателен.')
            return render_template('note_create.html')

        note = Note(
            title=title,
            content=content,
            user_id=current_user.id,
            is_favorite=is_favorite,
            category_id=category_id or None,
        )
        db.session.add(note)
        db.session.commit()

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            uploads_folder = current_app.config['UPLOAD_FOLDER']
            filepath = os.path.join(uploads_folder, filename).replace('\\', '/')
            file.save(filepath)

            attachment = Attachment(
                filename=filename,
                file_path=filepath,
                note_id=note.id
            )
            db.session.add(attachment)
            db.session.commit()

        flash('Заметка создана.')
        return redirect(url_for('notes.notes_index'))

    categories = Category.query.order_by(Category.name).all()
    return render_template('note_create.html', categories=categories)


@notes_bp.route('/<int:id>')
@login_required
def notes_view(id):
    note = Note.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template('note_view.html', note=note)


@notes_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def notes_edit(id):
    note = Note.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form.get('content', '')
        category_id = request.form.get('category_id')
        is_favorite = bool(request.form.get('is_favorite', False))
        file = request.files.get('file')

        if not title:
            flash('Заголовок обязателен.')
            return render_template('note_edit.html', note=note)

        note.title = title
        note.content = content
        note.category_id = category_id or None
        note.is_favorite = is_favorite
        note.updated_at = datetime.now()

        if file and file.filename and allowed_file(file.filename):
            old_attachments = note.attachments.all()
            for a in old_attachments:
                if os.path.exists(a.file_path):
                    os.remove(a.file_path)
                db.session.delete(a)

            filename = secure_filename(file.filename)
            uploads_folder = current_app.config['UPLOAD_FOLDER']
            filepath = os.path.join(uploads_folder, filename).replace('\\', '/')
            file.save(filepath)

            attachment = Attachment(
                filename=filename,
                file_path=filepath,
                note_id=note.id
            )
            db.session.add(attachment)

        db.session.commit()
        flash('Заметка обновлена.')
        return redirect(url_for('notes.notes_index'))

    categories = Category.query.order_by(Category.name).all()
    return render_template('note_edit.html', note=note, categories=categories)


@notes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def notes_delete(id):
    note = Note.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    for a in note.attachments:
        if os.path.exists(a.file_path):
            os.remove(a.file_path)
        db.session.delete(a)

    db.session.delete(note)
    db.session.commit()

    flash('Заметка удалена.')
    return redirect(url_for('notes.notes_index'))