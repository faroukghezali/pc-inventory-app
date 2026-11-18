"""
Inventory routes — all HTTP endpoints for the application.
No SQL here: delegate everything to app.models.database.
"""
from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify
)
from app.models.database import (
    get_all_models, get_total_count,
    get_items_by_slug, get_item_by_id, get_items_by_status,
    get_compatible_donors, execute_component_transfers, COMPONENT_LABELS,
    fan_exists, insert_item, update_item, bulk_insert_free,
    delete_item_by_id,
)

inventory_bp = Blueprint('inventory', __name__)

COMPONENT_ICONS = {
    'disque_dur': '💾',
    'ram': '🧠',
    'etat_clavier': '⌨️',
    'etat_ecran': '📺',
    'systeme_operateur': '🖥️',
    'ports_usb': '🔌',
    'batterie': '🔋',
}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@inventory_bp.route('/')
def index():
    models = get_all_models()
    total_pcs = get_total_count()
    return render_template('index.html', models=models, total_pcs=total_pcs)


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
        'has_details':       bool(r['disque_dur'] or r['etat_clavier'] or r['systeme_operateur'] or r['etat_ecran'] or (r['batterie'] is not None) or r['ram'] or r['ports_usb']),
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
        'has_details':       bool(r['disque_dur'] or r['etat_clavier'] or r['systeme_operateur'] or r['etat_ecran'] or (r['batterie'] is not None) or r['ram'] or r['ports_usb']),
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

        # ── Free: bulk insert ────────────────────────────────────────────
        if statut == 'Free':
            try:
                quantity = int(request.form.get('quantity', 1))
            except ValueError:
                quantity = 1
            quantity = max(1, min(quantity, 500))
            bulk_insert_free(slug, model_name, statut, quantity)
            return redirect(url_for('inventory.model_detail', slug=slug))

        # ── FAN uniqueness check ─────────────────────────────────────────
        fan = request.form.get('fan', '').strip() or None
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
        try:
            batterie = int(request.form.get('batterie', 0))
        except (ValueError, TypeError):
            batterie = None

        insert_item(
            slug, model_name, fan, sn, statut,
            username, code_user, license_num, obs,
            disque_dur, etat_clavier, systeme_operateur,
            etat_ecran, batterie, ram, ports_usb,
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
        try:
            batterie_raw = request.form.get('batterie')
            batterie = int(batterie_raw) if batterie_raw is not None and batterie_raw != '' else None
        except (ValueError, TypeError):
            batterie = None

        update_item(
            db_id, slug, model_name, fan, sn, statut,
            username, code_user, license_num, obs,
            disque_dur, etat_clavier, systeme_operateur,
            etat_ecran, batterie, ram, ports_usb,
        )
        flash('✅ Ordinateur mis à jour avec succès.', 'success')
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
