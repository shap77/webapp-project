import csv
from io import StringIO
from flask import Response
from flask_login import login_required, current_user
from models import Note
from . import export_bp


@export_bp.route('/export/txt')
@login_required
def notes_export_txt():
    user_id = current_user.id
    notes = Note.query.filter(Note.user_id == user_id).all()

    output = StringIO()
    for note in notes:
        output.write(f"Заголовок: {note.title}\n")
        output.write(f"Категория: {note.category.name if note.category else 'Без категории'}\n")
        output.write(f"Избранное: {'Да' if note.is_favorite else 'Нет'}\n")
        output.write(f"Дата: {note.created_at.strftime('%d.%m.%Y %H:%M')}\n")
        output.write(f"Текст: {note.content or '(пусто)'}\n")
        output.write("\n" + "-" * 60 + "\n\n")

    return Response(
        output.getvalue(),
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment;filename=notes_export.txt"},
    )


@export_bp.route('/export/csv')
@login_required
def notes_export_csv():
    user_id = current_user.id
    notes = Note.query.filter(Note.user_id == user_id).all()

    output = StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL)

    writer.writerow(["ID", "Заголовок", "Категория", "Избранное", "Дата", "Текст"])

    for note in notes:
        writer.writerow([
            note.id,
            note.title,
            note.category.name if note.category else "",
            "Да" if note.is_favorite else "Нет",
            note.created_at.strftime('%d.%m.%Y %H:%M'),
            note.content or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=notes_export.csv"},
    )