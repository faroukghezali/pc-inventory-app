"""
Inventory routes — all HTTP endpoints for the application.
No SQL here: delegate everything to app.models.database.
"""
from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify
)
from io import BytesIO
import os
import sqlite3
import tempfile
from flask import current_app, g, send_file
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from app.models.database import (
    get_all_models, get_total_count,
    get_items_by_slug, get_item_by_id, get_items_by_status,
    get_compatible_donors, execute_component_transfers, COMPONENT_LABELS,
    fan_exists, insert_item, update_item, bulk_insert_free,
    delete_item_by_id, delete_items_batch, get_all_inventory, get_status_summary,
    get_db,
)

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/admin/database/backup')
def database_backup():
    source = sqlite3.connect(current_app.config['DB_PATH'])
    snapshot = sqlite3.connect(':memory:')
    source.backup(snapshot)
    source.close()
    output = BytesIO()
    # Serialize the consistent SQLite snapshot, including committed data.
    output.write(snapshot.serialize())
    output.seek(0)
    snapshot.close()
    return send_file(output, mimetype='application/vnd.sqlite3', as_attachment=True,
                     download_name='inventory-backup.sqlite3')


@inventory_bp.route('/admin/database/restore', methods=['POST'])
def database_restore():
    upload = request.files.get('database')
    if not upload or not upload.filename:
        flash('Sélectionnez un fichier de sauvegarde SQLite.', 'error')
        return redirect(url_for('inventory.index'))
    temp_path = None
    check = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as temp:
            temp_path = temp.name
            upload.save(temp)
        check = sqlite3.connect(temp_path)
        valid = check.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        valid = valid and {'inventory', 'app_users'}.issubset(tables)
        if not valid:
            raise ValueError('Le fichier ne contient pas une base d’inventaire valide.')
        target_path = current_app.config['DB_PATH']
        current_db = g.pop('db', None)
        if current_db:
            current_db.close()
        target = sqlite3.connect(target_path)
        check.backup(target)
        target.close()
        check.close()
        flash('Base de données restaurée avec succès.', 'success')
    except (sqlite3.Error, ValueError) as error:
        flash(str(error) or 'Fichier SQLite invalide.', 'error')
    finally:
        if check:
            check.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
    return redirect(url_for('inventory.index'))

COMPONENT_ICONS = {
    'disque_dur': '💾',
    'ram': '🧠',
    'etat_clavier': '⌨️',
    'etat_ecran': '📺',
    'systeme_operateur': '🖥️',
    'ports_usb': '🔌',
    'batterie': '🔋',
}

ACCESSORY_CATEGORIES = {
    'disque-sauvegarde': 'Disque sauvegarde', 'casques': 'Casques',
    'clavier': 'Clavier', 'souris': 'Souris', 'telephones': 'Téléphones',
}


def accessory_category_name(category):
    """Name a known category, or an additional category already in inventory."""
    if category in ACCESSORY_CATEGORIES:
        return ACCESSORY_CATEGORIES[category]
    exists = get_db().execute(
        'SELECT 1 FROM accessories WHERE category = ? LIMIT 1', (category,)
    ).fetchone()
    if not exists:
        return None
    return category.replace('-', ' ').replace('_', ' ').title()


@inventory_bp.route('/accessoires/<category>')
def accessory_page(category):
    category_name = accessory_category_name(category)
    if not category_name:
        return redirect(url_for('inventory.index'))
    rows = get_db().execute('''SELECT id, brand, accessory_type, serial_number, phone_model, ram, storage,
        technical_details, created_at FROM accessories WHERE category = ? AND discharge_id IS NULL
        ORDER BY brand COLLATE NOCASE, phone_model COLLATE NOCASE, id''', (category,)).fetchall()
    brands = sorted({row['brand'] for row in rows}, key=str.casefold)
    return render_template('accessories.html', category=category, category_name=category_name, rows=rows, brands=brands, total=len(rows))


@inventory_bp.route('/accessoires/<category>/add', methods=['POST'])
def accessory_add(category):
    category_name = accessory_category_name(category)
    if not category_name:
        return redirect(url_for('inventory.index'))
    brand = request.form.get('brand', '').strip()
    is_phone = category == 'telephones'
    accessory_type = 'Téléphone' if is_phone else request.form.get('accessory_type', '')
    serial_number = request.form.get('serial_number', '').strip() or None
    phone_model = request.form.get('phone_model', '').strip() if is_phone else None
    ram = request.form.get('ram', '').strip() if is_phone else None
    storage = request.form.get('storage', '').strip() if is_phone else None
    technical_details = request.form.get('technical_details', '').strip() if is_phone else None
    try:
        quantity = int(request.form.get('quantity', '0'))
    except ValueError:
        quantity = 0
    invalid_phone = is_phone and (
        not phone_model or len(phone_model) > 100 or len(ram) > 60 or len(storage) > 60 or
        len(technical_details) > 500 or (serial_number and quantity != 1)
    )
    if not brand or len(brand) > 100 or (not is_phone and accessory_type not in {'USB/type-C', 'Bleutooth', 'USB', 'Type-C'}) or invalid_phone or quantity < 1 or quantity > 10000:
        if invalid_phone and serial_number and quantity != 1:
            flash('Pour saisir un numéro de série, la quantité doit être égale à 1.', 'error')
        elif invalid_phone:
            flash('Renseignez le modèle du téléphone et vérifiez les limites des champs.', 'error')
        else:
            flash('Saisissez une marque et une quantité entre 1 et 10 000.', 'error')
    else:
        get_db().executemany('''INSERT INTO accessories
            (category, brand, accessory_type, serial_number, phone_model, ram, storage, technical_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [(category, brand, accessory_type, serial_number, phone_model, ram, storage, technical_details)] * quantity)
        get_db().commit()
        flash(f'{quantity} article(s) {category_name} ajouté(s).', 'success')
    return redirect(url_for('inventory.accessory_page', category=category))


@inventory_bp.route('/accessoires/<category>/update', methods=['POST'])
def accessory_update(category):
    item_id = request.form.get('id', type=int)
    brand = request.form.get('brand', '').strip()
    accessory_type = request.form.get('accessory_type', '')
    serial_number = request.form.get('serial_number', '').strip() or None
    is_phone = category == 'telephones'
    phone_model = request.form.get('phone_model', '').strip() if is_phone else None
    ram = request.form.get('ram', '').strip() if is_phone else None
    storage = request.form.get('storage', '').strip() if is_phone else None
    technical_details = request.form.get('technical_details', '').strip() if is_phone else None
    invalid_phone = is_phone and (not phone_model or len(phone_model) > 100 or len(ram) > 60 or len(storage) > 60 or len(technical_details) > 500)
    if not accessory_category_name(category) or not item_id or not brand or len(brand) > 100 or invalid_phone or (not is_phone and accessory_type not in {'USB/type-C', 'Bleutooth', 'USB', 'Type-C'}):
        flash('Marque invalide.', 'error')
    elif is_phone:
        get_db().execute('''UPDATE accessories SET brand = ?, accessory_type = 'Téléphone', serial_number = ?,
            phone_model = ?, ram = ?, storage = ?, technical_details = ?
            WHERE id = ? AND category = ? AND discharge_id IS NULL''',
            (brand, serial_number, phone_model, ram, storage, technical_details, item_id, category))
        get_db().commit()
        flash('Téléphone modifié.', 'success')
    else:
        get_db().execute('UPDATE accessories SET brand = ?, accessory_type = ?, serial_number = ? WHERE id = ? AND category = ? AND discharge_id IS NULL', (brand, accessory_type, serial_number, item_id, category))
        get_db().commit()
        flash('Article modifié.', 'success')
    return redirect(url_for('inventory.accessory_page', category=category))


@inventory_bp.route('/accessoires/<category>/delete', methods=['POST'])
def accessory_delete(category):
    ids = [int(value) for value in request.form.getlist('ids') if value.isdigit()]
    if accessory_category_name(category) and ids:
        get_db().executemany('DELETE FROM accessories WHERE id = ? AND category = ? AND discharge_id IS NULL', [(item_id, category) for item_id in ids])
        get_db().commit()
        flash(f'{len(ids)} article(s) supprimé(s).', 'success')
    return redirect(url_for('inventory.accessory_page', category=category))


@inventory_bp.route('/decharges')
def discharge_index():
    db = get_db()
    records = db.execute("""SELECT d.id AS discharge_id, d.document_type, d.issued_at,
        COALESCE(d.recipient_name, i.username) AS display_user,
        COALESCE(d.recipient_code, i.code_user) AS display_code,
        i.id AS computer_id, i.fan,
        GROUP_CONCAT(CASE WHEN di.category = 'telephones' THEN 'Téléphone' ELSE di.category END || ': ' || di.brand || CASE WHEN di.phone_model IS NOT NULL THEN ' ' || di.phone_model ELSE '' END || CASE WHEN di.category = 'telephones' AND di.serial_number IS NOT NULL THEN ' · SN ' || di.serial_number ELSE '' END, ', ') AS taken_items
        FROM discharges d JOIN inventory i ON i.id=d.computer_id
        JOIN discharge_items di ON di.discharge_id=d.id AND di.returned_at IS NULL
        GROUP BY d.id ORDER BY d.id DESC""").fetchall()
    employees = db.execute("""SELECT id, model_name, fan, username, code_user FROM inventory
        WHERE statut IN ('Affecter', 'Utilisation hors domaine') AND
        (COALESCE(username, '') <> '' OR COALESCE(code_user, '') <> '')
        ORDER BY COALESCE(username, code_user) COLLATE NOCASE, id""").fetchall()
    return render_template('discharge_list.html', records=records, employees=employees)


@inventory_bp.route('/restitutions')
def restitution_index():
    records = get_db().execute("""SELECT r.id AS restitution_id, r.created_at AS issued_at,
        COALESCE(r.recipient_name, i.last_recipient, i.username,
            (SELECT d.recipient_name FROM discharges d WHERE d.computer_id=r.computer_id ORDER BY d.id DESC LIMIT 1)) AS display_user,
        COALESCE(r.recipient_code, i.code_user,
            (SELECT d.recipient_code FROM discharges d WHERE d.computer_id=r.computer_id ORDER BY d.id DESC LIMIT 1)) AS display_code,
        r.computer_returned, i.fan,
        GROUP_CONCAT(CASE WHEN ri.category = 'telephones' THEN 'Téléphone' ELSE ri.category END || ': ' || ri.brand || CASE WHEN ri.phone_model IS NOT NULL THEN ' ' || ri.phone_model ELSE '' END, ', ') AS returned_items
        FROM restitutions r JOIN inventory i ON i.id=r.computer_id
        LEFT JOIN restitution_items ri ON ri.restitution_id=r.id
        GROUP BY r.id ORDER BY r.id DESC""").fetchall()
    return render_template('discharge_list.html', records=records, movement='restitution')


@inventory_bp.route('/decharge/<int:item_id>')
def discharge_document(item_id):
    item = get_item_by_id(item_id)
    has_discharge = get_db().execute('SELECT 1 FROM discharges WHERE computer_id = ? LIMIT 1', (item_id,)).fetchone() if item else None
    if not item or (item.get('statut') not in {'Affecter', 'Utilisation hors domaine'} and not has_discharge):
        flash('Cette fiche de décharge est disponible pour les ordinateurs affectés ou hors domaine.', 'error')
        return redirect(url_for('inventory.discharge_index'))
    categories = {
        'casques': 'Casque', 'souris': 'Souris', 'clavier': 'Clavier',
        'disque-sauvegarde': 'Disque de sauvegarde', 'telephones': 'Téléphone',
    }
    accessories = {}
    for slug, label in categories.items():
        if slug == 'telephones':
            accessories[slug] = get_db().execute('''SELECT id, brand, phone_model, ram, storage, serial_number,
                CASE WHEN discharge_id IS NULL THEN 1 ELSE 0 END AS available_quantity
                FROM accessories WHERE category = ? ORDER BY brand COLLATE NOCASE, phone_model COLLATE NOCASE, id''', (slug,)).fetchall()
        else:
            accessories[slug] = get_db().execute('''SELECT brand, COUNT(*) AS total_quantity,
                SUM(CASE WHEN discharge_id IS NULL THEN 1 ELSE 0 END) AS available_quantity
                FROM accessories WHERE category = ? GROUP BY brand ORDER BY brand COLLATE NOCASE''', (slug,)).fetchall()
    return render_template('discharge.html', item=item, accessories=accessories, categories=categories, today=date.today().strftime('%d/%m/%Y'))


@inventory_bp.route('/decharge/<int:item_id>/confirm', methods=['POST'])
def discharge_confirm(item_id):
    item = get_item_by_id(item_id)
    if not item or item.get('statut') not in {'Affecter', 'Utilisation hors domaine'}:
        flash('Ordinateur non admissible pour une décharge.', 'error')
        return redirect(url_for('inventory.discharge_index'))
    categories = ['casques', 'souris', 'clavier', 'disque-sauvegarde', 'telephones']
    db = get_db()
    discharge_id = None
    saved = False
    try:
        db.execute('BEGIN IMMEDIATE')
        selected = [(category, request.form.get(f'brand_{category}', '').strip()) for category in categories if request.form.get(f'brand_{category}', '').strip()]
        if not selected:
            raise ValueError('Sélectionnez au moins un accessoire avant de valider la décharge.')
        discharge_id = db.execute("INSERT INTO discharges (computer_id, recipient_name, recipient_code, assignment_number, document_type) VALUES (?, ?, ?, ?, 'computer')", (item_id, item.get('username'), item.get('code_user'), item.get('assignment_number', 0))).lastrowid
        for category, value in selected:
            if category == 'telephones':
                phone_id = int(value) if value.isdigit() else 0
                cursor = db.execute('UPDATE accessories SET discharge_id = ? WHERE id = ? AND category = ? AND discharge_id IS NULL', (discharge_id, phone_id, category))
                accessory = db.execute('''SELECT id, brand, serial_number, phone_model, ram, storage, technical_details
                    FROM accessories WHERE id = ? AND discharge_id = ?''', (phone_id, discharge_id)).fetchone()
                brand = accessory['brand'] if accessory else value
            else:
                brand = value
                cursor = db.execute('''UPDATE accessories SET discharge_id = ? WHERE id = (
                    SELECT id FROM accessories WHERE category = ? AND brand = ? AND discharge_id IS NULL ORDER BY id LIMIT 1
                ) AND discharge_id IS NULL''', (discharge_id, category, brand))
                accessory = db.execute('''SELECT id, brand, serial_number, phone_model, ram, storage, technical_details
                    FROM accessories WHERE category = ? AND brand = ? AND discharge_id = ? ORDER BY id DESC LIMIT 1''', (category, brand, discharge_id)).fetchone()
            if cursor.rowcount != 1:
                raise ValueError(f'Rupture de stock pour {ACCESSORY_CATEGORIES[category]} — {brand}.')
            db.execute('''INSERT INTO discharge_items
                (discharge_id, accessory_id, category, brand, serial_number, phone_model, ram, storage, technical_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (discharge_id, accessory['id'], category, brand, accessory['serial_number'], accessory['phone_model'],
                 accessory['ram'], accessory['storage'], accessory['technical_details']))
        db.commit()
        saved = True
        flash('Accessoires attribués et décharge enregistrée.', 'success')
    except ValueError as error:
        db.rollback()
        flash(str(error), 'error')
    except sqlite3.Error:
        db.rollback()
        flash('Impossible d’enregistrer la décharge. Réessayez.', 'error')
    if saved:
        return redirect(url_for('inventory.discharge_record_document', discharge_id=discharge_id))
    return redirect(url_for('inventory.discharge_document', item_id=item_id))


@inventory_bp.route('/decharge/accessoires/<int:item_id>')
def accessory_discharge(item_id):
    item = get_item_by_id(item_id)
    if not item or item.get('statut') not in {'Affecter', 'Utilisation hors domaine'}:
        flash('Sélectionnez un employé actuellement affecté à un ordinateur.', 'error')
        return redirect(url_for('inventory.discharge_index'))
    stock = get_db().execute('''SELECT id, category, brand, accessory_type, serial_number, phone_model, ram, storage, technical_details FROM accessories
        WHERE discharge_id IS NULL ORDER BY category, brand COLLATE NOCASE, id''').fetchall()
    labels = {'casques': 'Casque', 'souris': 'Souris', 'clavier': 'Clavier', 'disque-sauvegarde': 'Disque de sauvegarde', 'telephones': 'Téléphone'}
    return render_template('accessory_discharge.html', item=item, stock=stock, categories=labels, today=date.today().strftime('%d/%m/%Y'))


@inventory_bp.route('/decharge/accessoires/<int:item_id>/confirm', methods=['POST'])
def accessory_discharge_confirm(item_id):
    item = get_item_by_id(item_id)
    if not item or item.get('statut') not in {'Affecter', 'Utilisation hors domaine'}:
        flash('Employé ou ordinateur non admissible pour une décharge.', 'error')
        return redirect(url_for('inventory.discharge_index'))
    accessory_ids = list(dict.fromkeys(int(value) for value in request.form.getlist('accessory_ids') if value.isdigit()))
    if not accessory_ids:
        flash('Sélectionnez au moins un accessoire.', 'error')
        return redirect(url_for('inventory.accessory_discharge', item_id=item_id))
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        placeholders = ','.join('?' for _ in accessory_ids)
        selected = db.execute(f'''SELECT id, category, brand, serial_number, phone_model, ram, storage, technical_details FROM accessories
            WHERE id IN ({placeholders}) AND discharge_id IS NULL ORDER BY id''', accessory_ids).fetchall()
        if len(selected) != len(accessory_ids):
            raise ValueError('Un ou plusieurs accessoires ne sont plus disponibles. Actualisez la page et réessayez.')
        discharge_id = db.execute("""INSERT INTO discharges
            (computer_id, recipient_name, recipient_code, assignment_number, document_type)
            VALUES (?, ?, ?, ?, 'accessories')""",
            (item_id, item.get('username'), item.get('code_user'), item.get('assignment_number', 0))).lastrowid
        for accessory in selected:
            changed = db.execute('UPDATE accessories SET discharge_id = ? WHERE id = ? AND discharge_id IS NULL', (discharge_id, accessory['id']))
            if changed.rowcount != 1:
                raise ValueError('Un accessoire vient d’être attribué. Actualisez la page et réessayez.')
            db.execute('''INSERT INTO discharge_items
                (discharge_id, accessory_id, category, brand, serial_number, phone_model, ram, storage, technical_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (discharge_id, accessory['id'], accessory['category'], accessory['brand'], accessory['serial_number'],
                 accessory['phone_model'], accessory['ram'], accessory['storage'], accessory['technical_details']))
        db.commit()
        flash('Décharge des accessoires enregistrée.', 'success')
        return redirect(url_for('inventory.discharge_record_document', discharge_id=discharge_id))
    except (sqlite3.Error, ValueError) as error:
        db.rollback()
        flash(str(error) if isinstance(error, ValueError) else 'Impossible d’enregistrer la décharge. Réessayez.', 'error')
        return redirect(url_for('inventory.accessory_discharge', item_id=item_id))


@inventory_bp.route('/decharge/document/<int:discharge_id>')
def discharge_record_document(discharge_id):
    db = get_db()
    record = db.execute('''SELECT d.id, d.document_type, d.issued_at, d.recipient_name, d.recipient_code,
        i.model_name, i.fan, i.sn FROM discharges d JOIN inventory i ON i.id=d.computer_id WHERE d.id=?''', (discharge_id,)).fetchone()
    if not record:
        flash('Cette décharge est introuvable.', 'error')
        return redirect(url_for('inventory.discharge_index'))
    issued = db.execute('SELECT category, brand, serial_number, phone_model, ram, storage, technical_details FROM discharge_items WHERE discharge_id=? ORDER BY id', (discharge_id,)).fetchall()
    categories = {'casques': 'Casque', 'souris': 'Souris', 'clavier': 'Clavier', 'disque-sauvegarde': 'Disque de sauvegarde', 'telephones': 'Téléphone'}
    return render_template('discharge_record.html', record=record, issued=issued, categories=categories,
                           today=date.today().strftime('%d/%m/%Y'))


@inventory_bp.route('/restitution/<int:item_id>', methods=['GET', 'POST'])
def restitution_document(item_id):
    item = get_item_by_id(item_id)
    if not item:
        return redirect(url_for('inventory.discharge_index'))
    db = get_db()
    if request.method == 'POST':
        if request.form.get('confirm_return') != 'yes':
            flash('Confirmez explicitement le retour avant de valider.', 'error')
            return redirect(url_for('inventory.restitution_document', item_id=item_id))
        accessory_ids = [int(value) for value in request.form.getlist('accessory_ids') if value.isdigit()]
        if not accessory_ids and item.get('statut') != 'En stock':
            flash('Sélectionnez au moins un accessoire retourné.', 'error')
            return redirect(url_for('inventory.restitution_document', item_id=item_id))
        try:
            db.execute('BEGIN IMMEDIATE')
            valid_events = []
            for accessory_id in dict.fromkeys(accessory_ids):
                event = db.execute('''SELECT di.category, di.brand, di.serial_number, di.discharge_id,
                    di.phone_model, di.ram, di.storage, di.technical_details
                    FROM discharge_items di JOIN accessories a ON a.id = di.accessory_id
                    JOIN discharges d ON d.id = di.discharge_id
                    WHERE di.accessory_id = ? AND di.returned_at IS NULL AND a.discharge_id = di.discharge_id AND d.computer_id = ?''', (accessory_id, item_id)).fetchone()
                if not event:
                    continue
                valid_events.append((accessory_id, event))
            if accessory_ids and not valid_events:
                raise ValueError('Aucun des accessoires sélectionnés n’est encore en attente de restitution.')
            previous_discharge = db.execute('''SELECT recipient_name, recipient_code FROM discharges
                WHERE computer_id=? ORDER BY id DESC LIMIT 1''', (item_id,)).fetchone()
            recipient_name = (previous_discharge['recipient_name'] if previous_discharge else None) or item.get('last_recipient') or item.get('username')
            recipient_code = (previous_discharge['recipient_code'] if previous_discharge else None) or item.get('code_user')
            restitution_id = db.execute('''INSERT INTO restitutions
                (computer_id, recipient_name, recipient_code, computer_returned) VALUES (?, ?, ?, ?)''',
                (item_id, recipient_name, recipient_code, int(item.get('statut') == 'En stock'))).lastrowid
            for accessory_id, event in valid_events:
                db.execute('UPDATE accessories SET discharge_id = NULL WHERE id = ?', (accessory_id,))
                db.execute('UPDATE discharge_items SET returned_at = CURRENT_TIMESTAMP WHERE accessory_id = ? AND returned_at IS NULL', (accessory_id,))
                db.execute('''INSERT INTO restitution_items
                    (restitution_id, category, brand, serial_number, phone_model, ram, storage, technical_details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (restitution_id, event['category'], event['brand'], event['serial_number'], event['phone_model'],
                     event['ram'], event['storage'], event['technical_details']))
            db.commit()
            flash('Retour enregistré et stock mis à jour.', 'success')
        except ValueError as error:
            db.rollback()
            flash(str(error), 'error')
        except (sqlite3.Error, TypeError):
            db.rollback()
            flash('Impossible d’enregistrer ce retour.', 'error')
        return redirect(url_for('inventory.restitution_document', item_id=item_id))
    outstanding = db.execute('''SELECT di.accessory_id, di.category, di.brand, di.serial_number,
        di.phone_model, di.ram, di.storage, di.technical_details FROM discharge_items di
        JOIN discharges d ON d.id = di.discharge_id WHERE d.computer_id = ? AND di.returned_at IS NULL ORDER BY di.id''', (item_id,)).fetchall()
    returned = db.execute('''SELECT category, brand, serial_number, phone_model, ram, storage, technical_details
        FROM restitution_items WHERE restitution_id = (SELECT id FROM restitutions WHERE computer_id = ? ORDER BY id DESC LIMIT 1) ORDER BY id''', (item_id,)).fetchall()
    previous_recipient = db.execute('SELECT recipient_name FROM discharges WHERE computer_id = ? ORDER BY id DESC LIMIT 1', (item_id,)).fetchone()
    recipient_name = (previous_recipient['recipient_name'] if previous_recipient and previous_recipient['recipient_name'] else None) or item.get('last_recipient') or item.get('username')
    return render_template('restitution.html', item=item, outstanding=outstanding, returned=returned, recipient_name=recipient_name, today=date.today().strftime('%d/%m/%Y'))


@inventory_bp.route('/restitution/document/<int:restitution_id>')
def restitution_record_document(restitution_id):
    db = get_db()
    record = db.execute('''SELECT r.id, r.created_at, r.recipient_name, r.recipient_code,
        r.computer_returned, i.model_name, i.fan, i.sn
        FROM restitutions r JOIN inventory i ON i.id=r.computer_id WHERE r.id=?''', (restitution_id,)).fetchone()
    if not record:
        flash('Cette restitution est introuvable.', 'error')
        return redirect(url_for('inventory.restitution_index'))
    returned = db.execute('''SELECT category, brand, serial_number, phone_model, ram, storage, technical_details FROM restitution_items
        WHERE restitution_id=? ORDER BY id''', (restitution_id,)).fetchall()
    return render_template('restitution_record.html', record=record, returned=returned,
                           today=date.today().strftime('%d/%m/%Y'))


@inventory_bp.route('/api/ai/inventory-analysis')
def ai_inventory_analysis():
    """Summarize issued, returned, and never-issued equipment for employees."""
    db = get_db()
    equipment = {
        'casques': 'Casque',
        'telephones': 'Téléphone',
        'disque-sauvegarde': 'Disque de sauvegarde',
    }
    people = {}

    def employee_key(name, code):
        normalized_code = (code or '').strip().casefold()
        if normalized_code:
            return 'code:' + normalized_code
        normalized_name = ' '.join((name or '').split()).casefold()
        return 'name:' + normalized_name if normalized_name else None

    def get_person(name, fan, code):
        key = employee_key(name, code)
        if not key:
            return None
        person = people.setdefault(key, {
            'full_name': '', 'fan': '', 'code_user': '', 'current': False,
            'issue_counts': {}, 'returned_counts': {}, 'restitution_counts': {},
        })
        if name and not person['full_name']:
            person['full_name'] = ' '.join(name.split())
        if fan and not person['fan']:
            person['fan'] = fan
        if code and not person['code_user']:
            person['code_user'] = code
        return person

    for row in db.execute('''SELECT username, fan, code_user FROM inventory
        WHERE statut IN ('Affecter', 'Utilisation hors domaine')
        AND (COALESCE(username, '') <> '' OR COALESCE(code_user, '') <> '')'''):
        person = get_person(row['username'], row['fan'], row['code_user'])
        if person:
            person['current'] = True

    issued_rows = db.execute('''SELECT d.recipient_name, d.recipient_code,
        i.username AS current_name, i.code_user AS current_code, i.fan,
        di.category, di.returned_at
        FROM discharges d JOIN inventory i ON i.id = d.computer_id
        JOIN discharge_items di ON di.discharge_id = d.id
        WHERE di.category IN ('casques', 'telephones', 'disque-sauvegarde')''').fetchall()
    for row in issued_rows:
        name = row['recipient_name'] or row['current_name']
        code = row['recipient_code'] or row['current_code']
        person = get_person(name, row['fan'], code)
        if not person:
            continue
        category = row['category']
        person['issue_counts'][category] = person['issue_counts'].get(category, 0) + 1
        if row['returned_at']:
            person['returned_counts'][category] = person['returned_counts'].get(category, 0) + 1

    returned_rows = db.execute('''SELECT r.recipient_name, r.recipient_code,
        i.username AS current_name, i.code_user AS current_code, i.fan, ri.category, COUNT(*) AS quantity
        FROM restitutions r JOIN inventory i ON i.id = r.computer_id
        JOIN restitution_items ri ON ri.restitution_id = r.id
        WHERE ri.category IN ('casques', 'telephones', 'disque-sauvegarde')
        GROUP BY r.id, ri.category''').fetchall()
    for row in returned_rows:
        name = row['recipient_name'] or row['current_name']
        code = row['recipient_code'] or row['current_code']
        person = get_person(name, row['fan'], code)
        if person:
            category = row['category']
            person['restitution_counts'][category] = person['restitution_counts'].get(category, 0) + row['quantity']

    results = []
    for person in people.values():
        for slug in equipment:
            person['issue_counts'][slug] = max(
                person['issue_counts'].get(slug, 0),
                person['restitution_counts'].get(slug, 0),
            )
        return_counts = {
            slug: max(person['returned_counts'].get(slug, 0), person['restitution_counts'].get(slug, 0))
            for slug in equipment
        }
        active_categories = {
            slug for slug, count in person['issue_counts'].items()
            if count > return_counts.get(slug, 0)
        }
        if not person['current'] and not active_categories:
            continue
        missing = [
            {'slug': slug, 'label': label}
            for slug, label in equipment.items()
            if not person['issue_counts'].get(slug, 0)
        ]
        issued = []
        for slug, label in equipment.items():
            if person['issue_counts'].get(slug, 0):
                statuses = []
                if slug in active_categories:
                    statuses.append('En dotation')
                if return_counts.get(slug, 0):
                    statuses.append('Restitué')
                issued.append({'slug': slug, 'label': label, 'statuses': statuses})
        if missing:
            results.append({
                'full_name': person['full_name'] or 'Nom non renseigné',
                'fan': person['fan'] or '—',
                'code_user': person['code_user'] or '—',
                'missing': missing,
                'issued': issued,
            })

    results.sort(key=lambda person: person['full_name'].casefold())
    return jsonify({
        'employees_scanned': sum(1 for person in people.values() if person['current'] or any(
            count > max(person['returned_counts'].get(slug, 0), person['restitution_counts'].get(slug, 0))
            for slug, count in person['issue_counts'].items()
        )),
        'employees_with_missing': len(results),
        'employees': results,
    })


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@inventory_bp.route('/', endpoint='index')
@inventory_bp.route('/dashboard')
def equipment_dashboard():
    """Centralized equipment directory, populated from the live inventory."""
    db = get_db()
    categories = db.execute('''
        SELECT category, COUNT(*) AS total_count
        FROM accessories
        WHERE discharge_id IS NULL
        GROUP BY category
        ORDER BY category COLLATE NOCASE
    ''').fetchall()
    category_counts = {row['category']: row['total_count'] for row in categories}
    known_categories = [
        {'slug': slug, 'name': label, 'total_count': category_counts.pop(slug, 0)}
        for slug, label in [
            ('casques', 'Casques'),
            ('souris', 'Souris'),
            ('clavier', 'Claviers'),
            ('disque-sauvegarde', 'Disques de sauvegarde'),
            ('telephones', 'Téléphones'),
        ]
    ]
    accessory_categories = known_categories + [{
        'slug': row['category'],
        'name': row['category'].replace('-', ' ').replace('_', ' ').title(),
        'total_count': category_counts[row['category']],
    } for row in categories if row['category'] in category_counts]
    return render_template(
        'equipment_dashboard.html',
        models=get_all_models(),
        total_pcs=get_total_count(),
        accessory_categories=accessory_categories,
        total_accessories=sum(category['total_count'] for category in accessory_categories),
    )


@inventory_bp.route('/ordinateurs')
def computer_models():
    """Show all registered computer models before opening a model inventory."""
    return render_template('computer_models.html', models=get_all_models())


# ---------------------------------------------------------------------------
# Préparer un PC — Ordinateurs En stock
# ---------------------------------------------------------------------------

@inventory_bp.route('/preparer')
def preparer_pc():
    rows = get_items_by_status('En stock')
    items = [{
        'db_id':             r['id'],
        'model_name':        r['model_name'],
        'model_slug':        r['model_slug'],
        'FAN':               r['fan'],
        'SN':                r['sn'],
        'Statut':            r['statut'],
        'Obs':               r['obs'],
        'batterie':          r['batterie'],
        'has_details':       bool(r['disque_dur'] or r['etat_clavier'] or r['systeme_operateur'] or r['etat_ecran'] or (r['batterie'] is not None) or r['ram'] or r['ports_usb'] or r['pave_tactile']),
    } for r in rows]
    return render_template('preparer_pc.html', items=items, total_stock=len(items))


# ---------------------------------------------------------------------------
# AI PC Preparation Engine API
# ---------------------------------------------------------------------------

@inventory_bp.route('/preparer/analyze/<int:db_id>')
def analyze_pc_preparation(db_id):
    target = get_item_by_id(db_id)
    if not target:
        return jsonify({'error': 'Ordinateur introuvable'}), 404

    slug = target['model_slug']
    donors = get_compatible_donors(slug, db_id)

    components_analysis = []
    total_defective = 0
    can_be_repaired = 0

    order = ['disque_dur', 'ram', 'etat_clavier', 'etat_ecran', 'systeme_operateur', 'ports_usb', 'batterie']

    for key in order:
        label = COMPONENT_LABELS[key]
        icon = COMPONENT_ICONS.get(key, '⚙️')
        cur_val = target.get(key)

        is_defective = False
        if key == 'batterie':
            is_defective = (cur_val is None or int(cur_val) < 50)
        elif key == 'ports_usb':
            is_defective = (cur_val != 'Toutes')
        else:
            is_defective = (cur_val != 'Oui')

        available_donors = []
        if is_defective:
            total_defective += 1
            for d in donors:
                d_val = d.get(key)
                valid = False
                if key == 'batterie':
                    valid = (d_val is not None and int(d_val) >= 50)
                elif key == 'ports_usb':
                    valid = (d_val == 'Toutes')
                else:
                    valid = (d_val == 'Oui')

                if valid:
                    available_donors.append({
                        'id': d['id'],
                        'sn': d['sn'] or 'Sans SN',
                        'fan': d['fan'] or 'Sans FAN',
                        'model_name': d['model_name'],
                        'value': d_val
                    })

            if key == 'batterie':
                available_donors.sort(key=lambda x: int(x['value']), reverse=True)

            if available_donors:
                can_be_repaired += 1

        components_analysis.append({
            'key': key,
            'name': label,
            'icon': icon,
            'is_defective': is_defective,
            'current_value': cur_val,
            'available_donors': available_donors,
            'recommended_donor': available_donors[0] if available_donors else None
        })

    return jsonify({
        'target': {
            'id': target['id'],
            'model_name': target['model_name'],
            'model_slug': target['model_slug'],
            'fan': target['fan'] or '—',
            'sn': target['sn'] or '—',
            'statut': target['statut'],
            'batterie': target['batterie'],
            'obs': target['obs'] or ''
        },
        'components': components_analysis,
        'total_defective': total_defective,
        'can_be_repaired': can_be_repaired,
        'compatible_donors_count': len(donors)
    })


@inventory_bp.route('/preparer/execute-transfer', methods=['POST'])
def execute_transfer():
    data = request.get_json() or {}
    target_id = data.get('target_id')
    transfers = data.get('transfers', {})

    if not target_id or not transfers:
        return jsonify({'success': False, 'message': 'Paramètres de transfert invalides.'}), 400

    try:
        result = execute_component_transfers(target_id, transfers)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Model detail / table view
# ---------------------------------------------------------------------------

@inventory_bp.route('/model/<slug>')
def model_detail(slug):
    rows = get_items_by_slug(slug)
    model_name = rows[0]['model_name'] if rows else slug.upper()

    items = [{
        'db_id':             r['id'],
        'FAN':               r['fan'],
        'SN':                r['sn'],
        'Statut':            r['statut'],
        "Nom d'utilisateur": r['username'],
        'Code User':         r['code_user'],
        'N° Licence':        r['license_num'],
        'Obs':               r['obs'],
        'disque_dur':        r['disque_dur'],
        'ram':               r['ram'],
        'etat_clavier':      r['etat_clavier'],
        'etat_ecran':        r['etat_ecran'],
        'systeme_operateur': r['systeme_operateur'],
        'ports_usb':         r['ports_usb'],
        'batterie':          r['batterie'],
        'has_details':       bool(r['disque_dur'] or r['etat_clavier'] or r['systeme_operateur'] or r['etat_ecran'] or (r['batterie'] is not None) or r['ram'] or r['ports_usb'] or r['pave_tactile']),
    } for r in rows]

    model_data = {
        'name':        model_name,
        'slug':        slug,
        'total_count': len(items),
        'rows':        items,
    }
    return render_template('model_detail.html', model=model_data)


# ---------------------------------------------------------------------------
# Item details API  (JSON — used by the popup)
# ---------------------------------------------------------------------------

@inventory_bp.route('/item/<int:db_id>/details')
def item_details(db_id):
    row = get_item_by_id(db_id)
    if not row:
        return jsonify({'error': 'Not found'}), 404
    # Return only the hardware-detail fields
    return jsonify({
        'fan':                row.get('fan'),
        'sn':                 row.get('sn'),
        'model_name':         row.get('model_name'),
        'statut':             row.get('statut'),
        'disque_dur':         row.get('disque_dur'),
        'etat_clavier':       row.get('etat_clavier'),
        'systeme_operateur':  row.get('systeme_operateur'),
        'etat_ecran':         row.get('etat_ecran'),
        'batterie':           row.get('batterie'),
        'ram':                row.get('ram'),
        'ports_usb':          row.get('ports_usb'),
        'pave_tactile':       row.get('pave_tactile'),
        'obs':                row.get('obs'),
    })


# ---------------------------------------------------------------------------
# Add computer
# ---------------------------------------------------------------------------

@inventory_bp.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        model_name = request.form.get('model_name', '').strip()
        statut     = request.form.get('statut', '').strip()
        slug       = model_name.lower().replace(' ', '-')

        fan = request.form.get('fan', '').strip() or None
        if statut == 'Créé' and not fan:
            flash('Le numéro FAN est obligatoire pour un ordinateur créé.', 'error')
            return render_template('add_item.html', form_data=request.form)

        # ── Free: bulk insert ────────────────────────────────────────────
        if statut == 'Free':
            try:
                quantity = int(request.form.get('quantity', 1))
            except ValueError:
                quantity = 1
            quantity = max(1, min(quantity, 500))
            serial_number = request.form.get('sn', '').strip() or None
            bulk_insert_free(slug, model_name, statut, quantity, serial_number)
            return redirect(url_for('inventory.model_detail', slug=slug))

        # ── FAN uniqueness check ─────────────────────────────────────────
        if fan and fan_exists(fan):
            flash(
                f'❌ Le numéro FAN « {fan} » existe déjà. Veuillez en saisir un autre.',
                'error'
            )
            return render_template('add_item.html', form_data=request.form)

        sn          = request.form.get('sn',          '').strip() or None
        username    = request.form.get('username',    '').strip() or None
        code_user   = request.form.get('code_user',   '').strip() or None
        license_num = request.form.get('license_num', '').strip() or None
        obs         = request.form.get('obs',         '').strip() or None

        # ── Hardware details (En stock only) ─────────────────────────────
        disque_dur        = request.form.get('disque_dur')        or None
        etat_clavier      = request.form.get('etat_clavier')      or None
        systeme_operateur = request.form.get('systeme_operateur') or None
        etat_ecran        = request.form.get('etat_ecran')        or None
        ram               = request.form.get('ram')               or None
        ports_usb         = request.form.get('ports_usb')         or None
        pave_tactile      = request.form.get('pave_tactile')      or None
        try:
            batterie = int(request.form.get('batterie', 0))
        except (ValueError, TypeError):
            batterie = None

        insert_item(
            slug, model_name, fan, sn, statut,
            username, code_user, license_num, obs,
            disque_dur, etat_clavier, systeme_operateur,
            etat_ecran, batterie, ram, ports_usb,
            pave_tactile=pave_tactile,
        )
        return redirect(url_for('inventory.model_detail', slug=slug))

    return render_template('add_item.html', form_data={})


# ---------------------------------------------------------------------------
# Update / Edit computer
# ---------------------------------------------------------------------------

@inventory_bp.route('/edit/<int:db_id>', methods=['GET', 'POST'])
def edit_item(db_id):
    item = get_item_by_id(db_id)
    if not item:
        flash('❌ Ordinateur introuvable.', 'error')
        return redirect(url_for('inventory.index'))

    if request.method == 'POST':
        model_name = request.form.get('model_name', '').strip()
        statut     = request.form.get('statut', '').strip()
        slug       = model_name.lower().replace(' ', '-')

        # ── FAN uniqueness check (excluding current item) ────────────────
        fan = request.form.get('fan', '').strip() or None
        if statut == 'Créé' and not fan:
            flash('Le numéro FAN est obligatoire pour un ordinateur créé.', 'error')
            form_data = dict(item)
            form_data.update(request.form)
            return render_template('edit_item.html', item=form_data)
        if fan and fan_exists(fan, exclude_id=db_id):
            flash(
                f'❌ Le numéro FAN « {fan} » existe déjà pour un autre ordinateur.',
                'error'
            )
            form_data = dict(request.form)
            form_data['id'] = db_id
            return render_template('edit_item.html', item=form_data)

        sn          = request.form.get('sn',          '').strip() or None
        username    = request.form.get('username',    '').strip() or None
        code_user   = request.form.get('code_user',   '').strip() or None
        license_num = request.form.get('license_num', '').strip() or None
        obs         = request.form.get('obs',         '').strip() or None

        # ── Hardware & system details ────────────────────────────────────
        disque_dur        = request.form.get('disque_dur')        or None
        etat_clavier      = request.form.get('etat_clavier')      or None
        systeme_operateur = request.form.get('systeme_operateur') or None
        etat_ecran        = request.form.get('etat_ecran')        or None
        ram               = request.form.get('ram')               or None
        ports_usb         = request.form.get('ports_usb')         or None
        pave_tactile      = request.form.get('pave_tactile')      or None
        try:
            batterie_raw = request.form.get('batterie')
            batterie = int(batterie_raw) if batterie_raw is not None and batterie_raw != '' else None
        except (ValueError, TypeError):
            batterie = None

        if item.get('statut') in {'Free', 'Créé'} and statut == 'Affecter':
            disque_dur = disque_dur or 'Oui'
            etat_clavier = etat_clavier or 'Oui'
            systeme_operateur = systeme_operateur or 'Oui'
            etat_ecran = etat_ecran or 'Oui'
            ram = ram or 'Oui'
            ports_usb = ports_usb or 'Toutes'
            pave_tactile = pave_tactile or 'Oui'
            batterie = batterie if batterie is not None else 100

        update_item(
            db_id, slug, model_name, fan, sn, statut,
            username, code_user, license_num, obs,
            disque_dur, etat_clavier, systeme_operateur,
            etat_ecran, batterie, ram, ports_usb,
            pave_tactile=pave_tactile,
        )
        if statut in {'Affecter', 'Utilisation hors domaine'} and (
            item.get('statut') not in {'Affecter', 'Utilisation hors domaine'}
            or item.get('username') != username or item.get('code_user') != code_user
        ):
            get_db().execute('UPDATE inventory SET assignment_number = assignment_number + 1 WHERE id = ?', (db_id,))
            get_db().commit()
        flash('✅ Ordinateur mis à jour avec succès.', 'success')
        if item.get('statut') == 'Affecter' and statut == 'En stock':
            get_db().execute('UPDATE inventory SET last_recipient = ? WHERE id = ?', (item.get('username'), db_id))
            get_db().commit()
            return redirect(url_for('inventory.restitution_document', item_id=db_id))
        if statut in {'Affecter', 'Utilisation hors domaine'} and item.get('statut') != statut:
            return redirect(url_for('inventory.discharge_document', item_id=db_id))
        return redirect(url_for('inventory.model_detail', slug=slug))

    return render_template('edit_item.html', item=item)


# ---------------------------------------------------------------------------
# Delete computer
# ---------------------------------------------------------------------------

@inventory_bp.route('/delete/<int:db_id>', methods=['POST'])
def delete_item(db_id):
    slug = delete_item_by_id(db_id)
    if slug:
        return redirect(url_for('inventory.model_detail', slug=slug))
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/delete-batch', methods=['POST'])
def delete_batch():
    ids = [int(value) for value in request.form.getlist('ids') if value.isdigit()]
    slugs = delete_items_batch(ids)
    return redirect(url_for('inventory.model_detail', slug=slugs[0]) if len(slugs) == 1 else url_for('inventory.index'))


@inventory_bp.route('/export/excel')
def export_excel():
    records = get_all_inventory()
    selected_ids = {int(value) for value in request.args.getlist('ids') if value.isdigit()}
    if selected_ids:
        records = [record for record in records if record['id'] in selected_ids]
    counts = {}
    for record in records:
        if record.get('statut'):
            counts[record['statut']] = counts.get(record['statut'], 0) + 1
    total = len(records)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Inventaire'
    ws.merge_cells('A1:Q1')
    ws['A1'] = 'PSA STELLANTIS'
    ws['A1'].font = Font(name='Aptos Display', size=20, bold=True, color='FFFFFF')
    ws['A1'].fill = PatternFill('solid', fgColor='17365D')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 34
    ws.merge_cells('A2:Q2')
    ws['A2'] = "Rapport d'inventaire parc IT"
    ws['A2'].font = Font(size=14, bold=True, color='17365D')
    ws['A2'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A3:Q3')
    ws['A3'] = f'Date : {date.today().strftime("%d/%m/%Y")}'
    ws['A3'].alignment = Alignment(horizontal='right')
    ws.merge_cells('A4:Q4')
    ws['A4'] = 'Ordinateurs sélectionnés' if selected_ids else 'Inventaire complet du parc informatique'
    fields = [
        ('model_name', 'Modèle'), ('fan', 'Numéro FAN'), ('sn', 'SN'),
        ('statut', 'Statut'), ('username', 'Utilisateur'), ('code_user', 'Code User'),
        ('license_num', 'Licence'), ('obs', 'Observations'), ('disque_dur', 'Disque dur'),
        ('ram', 'RAM'), ('etat_clavier', 'Clavier'), ('etat_ecran', 'Écran'),
        ('systeme_operateur', 'Système opérateur'), ('ports_usb', 'Ports USB'),
        ('batterie', 'Batterie (%)'), ('pave_tactile', 'Pavé tactile'), ('id', 'ID'),
    ]
    headers = [label for _, label in fields]
    header_row = 6
    for col, label in enumerate(headers, 1):
        cell = ws.cell(header_row, col, label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2874A6')
        cell.alignment = Alignment(horizontal='center')
    thin = Side(style='thin', color='AAB7B8')
    for record in records:
        values = [record.get(field) if record.get(field) is not None else '' for field, _ in fields]
        ws.append(values)
    for row in ws.iter_rows(min_row=header_row, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if cell.row > header_row and cell.row % 2 == 1:
                cell.fill = PatternFill('solid', fgColor='F2F6FA')
    for col, (_, label) in enumerate(fields, 1):
        ws.column_dimensions[get_column_letter(col)].width = max(16, min(30, len(label) + 4))
    ws.freeze_panes = 'A7'
    ws.auto_filter.ref = f'A{header_row}:Q{ws.max_row}'

    summary = wb.create_sheet('Résumé')
    summary.merge_cells('A1:B1')
    summary['A1'] = 'Résumé de l’inventaire'
    summary['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    summary['A1'].fill = PatternFill('solid', fgColor='17365D')
    summary['A1'].alignment = Alignment(horizontal='center')
    for col, label in enumerate(['Status', 'Total'], 1):
        cell = summary.cell(3, col, label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2874A6')
    statuses = ['En stock', 'Affecter', 'Créé', 'Utilisation hors domaine', 'Free']
    for status in statuses:
        summary.append([status, counts.get(status, 0)])
    summary.append(['Total général', total])
    for row in summary.iter_rows(min_row=3, max_row=summary.max_row, min_col=1, max_col=2):
        for cell in row:
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    summary['A9'].font = Font(bold=True)
    summary['B9'].font = Font(bold=True)
    summary.column_dimensions['A'].width = 32
    summary.column_dimensions['B'].width = 16
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='rapport_inventaire_it.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
