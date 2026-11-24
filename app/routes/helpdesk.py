"""Public employee Helpdesk and administrator request management."""
from datetime import datetime, timezone
from io import BytesIO
from functools import wraps

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, send_file, url_for)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.models.database import get_db

helpdesk_bp = Blueprint('helpdesk', __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, 'current_user', None) or not g.current_user['is_admin']:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@helpdesk_bp.route('/helpdesk', methods=['GET', 'POST'])
def submit_request():
    error = None
    submitted_id = request.args.get('submitted', type=int)
    submitted = bool(submitted_id and get_db().execute(
        'SELECT id FROM helpdesk_requests WHERE id = ?', (submitted_id,),
    ).fetchone())
    if request.method == 'POST':
        code_user = request.form.get('code_user', '').strip()
        description = request.form.get('description', '').strip()
        if not code_user or len(code_user) > 80:
            error = 'Enter a valid Code User (up to 80 characters).'
        elif not description or len(description) > 5000:
            error = 'Describe the issue in up to 5,000 characters.'
        else:
            db = get_db()
            cursor = db.execute(
                'INSERT INTO helpdesk_requests (code_user, description) VALUES (?, ?)',
                (code_user, description),
            )
            db.commit()
            return redirect(url_for('helpdesk.submit_request', submitted=cursor.lastrowid))
    return render_template(
        'helpdesk.html', submitted=submitted, error=error,
        code_user=request.form.get('code_user', ''), description=request.form.get('description', ''),
    )


@helpdesk_bp.route('/helpdesk/management')
@admin_required
def management():
    status = request.args.get('status', 'all')
    if status not in {'all', 'En attente', 'Résolu'}:
        status = 'all'
    db = get_db()
    if status == 'all':
        rows = db.execute('SELECT * FROM helpdesk_requests ORDER BY submitted_at DESC, id DESC').fetchall()
    else:
        rows = db.execute(
            'SELECT * FROM helpdesk_requests WHERE status = ? ORDER BY submitted_at DESC, id DESC',
            (status,),
        ).fetchall()
    counts = {
        'all': db.execute('SELECT COUNT(*) FROM helpdesk_requests').fetchone()[0],
        'pending': db.execute("SELECT COUNT(*) FROM helpdesk_requests WHERE status = 'En attente'").fetchone()[0],
        'resolved': db.execute("SELECT COUNT(*) FROM helpdesk_requests WHERE status = 'Résolu'").fetchone()[0],
    }
    setting = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = 'activity_log_retention_days'"
    ).fetchone()
    retention_days = int(setting['setting_value']) if setting and setting['setting_value'] in {'7', '14'} else 7
    return render_template('helpdesk_management.html', requests=rows, status=status, counts=counts,
                           activity_log_retention_days=retention_days)


@helpdesk_bp.route('/helpdesk/management/<int:request_id>/delete', methods=['POST'])
@admin_required
def delete_request(request_id):
    db = get_db()
    cursor = db.execute('DELETE FROM helpdesk_requests WHERE id = ?', (request_id,))
    db.commit()
    flash('Helpdesk request deleted.' if cursor.rowcount else 'Request not found.',
          'success' if cursor.rowcount else 'error')
    return redirect(url_for('helpdesk.management'))


@helpdesk_bp.route('/helpdesk/management/activity-log-retention', methods=['POST'])
@admin_required
def update_activity_log_retention():
    value = request.form.get('retention_days', '')
    if value not in {'7', '14'}:
        flash('Choose a retention period of 7 or 14 days.', 'error')
    else:
        db = get_db()
        db.execute('''INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('activity_log_retention_days', ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value''', (value,))
        db.commit()
        flash(f'Activity log retention set to {value} days.', 'success')
    return redirect(url_for('helpdesk.management'))


@helpdesk_bp.route('/helpdesk/management/export/<report_format>')
@admin_required
def export_statistics(report_format):
    if report_format not in {'xlsx', 'txt'}:
        abort(404)
    db = get_db()
    counts = {
        'total': db.execute('SELECT COUNT(*) FROM helpdesk_requests').fetchone()[0],
        'resolved': db.execute("SELECT COUNT(*) FROM helpdesk_requests WHERE status = 'Résolu'").fetchone()[0],
        'pending': db.execute("SELECT COUNT(*) FROM helpdesk_requests WHERE status = 'En attente'").fetchone()[0],
    }
    counts['resolution_rate'] = round(counts['resolved'] * 100 / counts['total'], 1) if counts['total'] else 0
    bounds = db.execute('SELECT MIN(submitted_at), MAX(submitted_at) FROM helpdesk_requests').fetchone()
    monthly_rows = db.execute('''SELECT substr(submitted_at, 1, 7) AS month, status, COUNT(*) AS quantity
        FROM helpdesk_requests GROUP BY substr(submitted_at, 1, 7), status
        ORDER BY month''').fetchall()
    monthly = {}
    for row in monthly_rows:
        month = row['month'] or 'Unknown date'
        monthly.setdefault(month, {'total': 0, 'resolved': 0, 'pending': 0})
        monthly[month]['total'] += row['quantity']
        monthly[month]['resolved' if row['status'] == 'Résolu' else 'pending'] += row['quantity']
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    filename_date = datetime.now(timezone.utc).strftime('%Y%m%d')

    if report_format == 'txt':
        lines = [
            'HELPDESK STATISTICS',
            f'Generated: {generated}',
            '',
            f"Total requests: {counts['total']}",
            f"Resolved: {counts['resolved']}",
            f"Pending: {counts['pending']}",
            f"Resolution rate: {counts['resolution_rate']}%",
            f'First request: {bounds[0] or "N/A"}',
            f'Latest request: {bounds[1] or "N/A"}',
            '',
            'MONTHLY BREAKDOWN',
            'Month | Total | Resolved | Pending',
        ]
        lines.extend(f'{month} | {values["total"]} | {values["resolved"]} | {values["pending"]}'
                     for month, values in monthly.items())
        content = ('\n'.join(lines) + '\n').encode('utf-8')
        return send_file(BytesIO(content), mimetype='text/plain; charset=utf-8', as_attachment=True,
                         download_name=f'helpdesk-statistics-{filename_date}.txt')

    workbook = Workbook()
    summary = workbook.active
    summary.title = 'Summary'
    summary.append(['Helpdesk Statistics', 'Value'])
    summary.append(['Generated', generated])
    summary.append(['Total requests', counts['total']])
    summary.append(['Resolved', counts['resolved']])
    summary.append(['Pending', counts['pending']])
    summary.append(['Resolution rate (%)', counts['resolution_rate']])
    summary.append(['First request', bounds[0] or 'N/A'])
    summary.append(['Latest request', bounds[1] or 'N/A'])
    summary.freeze_panes = 'A2'
    summary.column_dimensions['A'].width = 25
    summary.column_dimensions['B'].width = 32
    for cell in summary[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='123A56')
    monthly_sheet = workbook.create_sheet('Monthly')
    monthly_sheet.append(['Month', 'Total requests', 'Resolved', 'Pending'])
    for month, values in monthly.items():
        monthly_sheet.append([month, values['total'], values['resolved'], values['pending']])
    monthly_sheet.freeze_panes = 'A2'
    for column, width in {'A': 18, 'B': 20, 'C': 15, 'D': 15}.items():
        monthly_sheet.column_dimensions[column].width = width
    for cell in monthly_sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='123A56')
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'helpdesk-statistics-{filename_date}.xlsx')


@helpdesk_bp.route('/helpdesk/management/<int:request_id>')
@admin_required
def request_detail(request_id):
    support_request = get_db().execute(
        'SELECT * FROM helpdesk_requests WHERE id = ?', (request_id,),
    ).fetchone()
    if not support_request:
        abort(404)
    return render_template('helpdesk_detail.html', support_request=support_request)


@helpdesk_bp.route('/helpdesk/management/<int:request_id>/resolve', methods=['POST'])
@admin_required
def resolve_request(request_id):
    db = get_db()
    db.execute(
        "UPDATE helpdesk_requests SET status = 'Résolu', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (request_id,),
    )
    db.commit()
    return redirect(url_for('helpdesk.request_detail', request_id=request_id))
