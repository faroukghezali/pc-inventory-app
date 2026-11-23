"""
Database layer — connection, initialisation, and all data-access helpers.
All SQL lives here; routes never touch sqlite3 directly.
"""
import sqlite3
from datetime import datetime
from flask import current_app, g


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def get_db():
    """Return the per-request DB connection (cached in Flask's g)."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DB_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Schema initialisation  (safe: ALTER TABLE if columns missing)
# ---------------------------------------------------------------------------

def init_db():
    """Create / migrate the inventory table."""
    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path)

    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            model_slug         TEXT    NOT NULL,
            model_name         TEXT    NOT NULL,
            fan                TEXT    UNIQUE,
            sn                 TEXT,
            statut             TEXT,
            assignment_number  INTEGER NOT NULL DEFAULT 0,
            last_recipient     TEXT,
            username           TEXT,
            code_user          TEXT,
            license_num        TEXT,
            obs                TEXT,
            disque_dur         TEXT,
            etat_clavier       TEXT,
            systeme_operateur  TEXT,
            etat_ecran         TEXT,
            batterie           INTEGER,
            ram                TEXT,
            ports_usb          TEXT,
            pave_tactile       TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            access_level TEXT NOT NULL CHECK(access_level IN ('read', 'write', 'full')),
            is_admin INTEGER NOT NULL DEFAULT 0,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS accessories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            accessory_type TEXT NOT NULL DEFAULT 'USB',
            serial_number TEXT,
            discharge_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    accessory_columns = {r[1] for r in conn.execute('PRAGMA table_info(accessories)').fetchall()}
    if 'accessory_type' not in accessory_columns:
        conn.execute("ALTER TABLE accessories ADD COLUMN accessory_type TEXT NOT NULL DEFAULT 'USB'")
    conn.execute("UPDATE accessories SET accessory_type = 'USB' WHERE accessory_type = 'Bluetooth/USB'")
    conn.execute("UPDATE accessories SET accessory_type = 'Type-C' WHERE accessory_type = 'Type-C/USB'")
    if 'serial_number' not in accessory_columns:
        conn.execute('ALTER TABLE accessories ADD COLUMN serial_number TEXT')
    if 'discharge_id' not in accessory_columns:
        conn.execute('ALTER TABLE accessories ADD COLUMN discharge_id INTEGER')
    for col in ('phone_model', 'ram', 'storage', 'technical_details'):
        if col not in accessory_columns:
            conn.execute(f'ALTER TABLE accessories ADD COLUMN {col} TEXT')
    conn.execute('''CREATE TABLE IF NOT EXISTS discharges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        computer_id INTEGER NOT NULL,
        recipient_name TEXT,
        recipient_code TEXT,
        issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    discharge_columns = {r[1] for r in conn.execute('PRAGMA table_info(discharges)').fetchall()}
    if 'assignment_number' not in discharge_columns:
        conn.execute('ALTER TABLE discharges ADD COLUMN assignment_number INTEGER NOT NULL DEFAULT 0')
    if 'recipient_name' not in discharge_columns:
        conn.execute('ALTER TABLE discharges ADD COLUMN recipient_name TEXT')
    if 'recipient_code' not in discharge_columns:
        conn.execute('ALTER TABLE discharges ADD COLUMN recipient_code TEXT')
    if 'document_type' not in discharge_columns:
        conn.execute("ALTER TABLE discharges ADD COLUMN document_type TEXT NOT NULL DEFAULT 'computer'")
    conn.execute('''CREATE TABLE IF NOT EXISTS discharge_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discharge_id INTEGER NOT NULL,
        accessory_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        brand TEXT NOT NULL,
        serial_number TEXT,
        returned_at TEXT,
        UNIQUE(discharge_id, accessory_id)
    )''')
    discharge_item_columns = {r[1] for r in conn.execute('PRAGMA table_info(discharge_items)').fetchall()}
    for col in ('phone_model', 'ram', 'storage', 'technical_details'):
        if col not in discharge_item_columns:
            conn.execute(f'ALTER TABLE discharge_items ADD COLUMN {col} TEXT')
    conn.execute('''CREATE TABLE IF NOT EXISTS restitutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        computer_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    restitution_columns = {r[1] for r in conn.execute('PRAGMA table_info(restitutions)').fetchall()}
    if 'recipient_name' not in restitution_columns:
        conn.execute('ALTER TABLE restitutions ADD COLUMN recipient_name TEXT')
    if 'recipient_code' not in restitution_columns:
        conn.execute('ALTER TABLE restitutions ADD COLUMN recipient_code TEXT')
    if 'computer_returned' not in restitution_columns:
        conn.execute('ALTER TABLE restitutions ADD COLUMN computer_returned INTEGER NOT NULL DEFAULT 0')
    conn.execute('''CREATE TABLE IF NOT EXISTS restitution_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restitution_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        brand TEXT NOT NULL,
        serial_number TEXT
    )''')
    restitution_item_columns = {r[1] for r in conn.execute('PRAGMA table_info(restitution_items)').fetchall()}
    for col in ('phone_model', 'ram', 'storage', 'technical_details'):
        if col not in restitution_item_columns:
            conn.execute(f'ALTER TABLE restitution_items ADD COLUMN {col} TEXT')
    conn.execute('''INSERT OR IGNORE INTO discharge_items (discharge_id, accessory_id, category, brand, serial_number)
        SELECT discharge_id, id, category, brand, serial_number FROM accessories WHERE discharge_id IS NOT NULL''')

    # Safe migration: add new columns to existing DBs
    existing = {r[1] for r in conn.execute('PRAGMA table_info(inventory)').fetchall()}
    if 'last_recipient' not in existing:
        conn.execute('ALTER TABLE inventory ADD COLUMN last_recipient TEXT')
    if 'assignment_number' not in existing:
        conn.execute('ALTER TABLE inventory ADD COLUMN assignment_number INTEGER NOT NULL DEFAULT 0')
    user_columns = {r[1] for r in conn.execute('PRAGMA table_info(app_users)').fetchall()}
    if 'email' not in user_columns:
        conn.execute('ALTER TABLE app_users ADD COLUMN email TEXT')
    new_cols = [
        ('disque_dur',         'TEXT'),
        ('etat_clavier',       'TEXT'),
        ('systeme_operateur',  'TEXT'),
        ('etat_ecran',         'TEXT'),
        ('batterie',           'INTEGER'),
        ('ram',                'TEXT'),
        ('ports_usb',          'TEXT'),
        ('pave_tactile',       'TEXT'),
    ]
    for col, typ in new_cols:
        if col not in existing:
            conn.execute(f'ALTER TABLE inventory ADD COLUMN {col} {typ}')

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_all_models():
    db = get_db()
    rows = db.execute('''
        SELECT model_slug, model_name, COUNT(*) AS total_count
        FROM inventory
        GROUP BY model_slug, model_name
        ORDER BY model_name
    ''').fetchall()
    return [
        {'slug': r['model_slug'], 'name': r['model_name'], 'total_count': r['total_count']}
        for r in rows
    ]


def get_total_count():
    db = get_db()
    return db.execute('SELECT COUNT(*) FROM inventory').fetchone()[0]


def get_items_by_slug(slug):
    db = get_db()
    rows = db.execute(
        'SELECT * FROM inventory WHERE model_slug = ? ORDER BY id',
        (slug,)
    ).fetchall()
    return rows


def get_items_by_status(status):
    """Return all computers having a specific status (e.g. 'En stock')."""
    db = get_db()
    rows = db.execute(
        'SELECT * FROM inventory WHERE statut = ? ORDER BY id DESC',
        (status,)
    ).fetchall()
    return rows


def get_item_by_id(db_id):
    """Return a single row as a dict (for the details popup API)."""
    db = get_db()
    row = db.execute('SELECT * FROM inventory WHERE id = ?', (db_id,)).fetchone()
    return dict(row) if row else None


def get_all_inventory():
    """Return all inventory records sorted by model_name, id."""
    db = get_db()
    rows = db.execute('''
        SELECT * FROM inventory
        ORDER BY model_name COLLATE NOCASE ASC, id ASC
    ''').fetchall()
    return [dict(r) for r in rows]


def get_status_summary():
    """Return count per status and total general."""
    db = get_db()
    rows = db.execute('''
        SELECT statut, COUNT(*) AS count
        FROM inventory
        GROUP BY statut
    ''').fetchall()
    counts = {r['statut']: r['count'] for r in rows if r['statut']}
    total = db.execute('SELECT COUNT(*) FROM inventory').fetchone()[0]
    return counts, total


def fan_exists(fan, exclude_id=None):
    """Return True if the given FAN is already in the database (excluding exclude_id)."""
    db = get_db()
    if exclude_id is not None:
        return db.execute(
            'SELECT 1 FROM inventory WHERE fan = ? AND id != ?', (fan, exclude_id)
        ).fetchone() is not None
    return db.execute(
        'SELECT 1 FROM inventory WHERE fan = ?', (fan,)
    ).fetchone() is not None


def insert_item(model_slug, model_name, fan, sn, statut,
                username, code_user, license_num, obs,
                disque_dur=None, etat_clavier=None, systeme_operateur=None,
                etat_ecran=None, batterie=None, ram=None, ports_usb=None,
                pave_tactile=None):
    # Automatic Component Status: Créé or Free PCs are new/fully functional
    if statut in ('Créé', 'Free'):
        disque_dur = 'Oui'
        ram = 'Oui'
        etat_clavier = 'Oui'
        etat_ecran = 'Oui'
        systeme_operateur = 'Oui'
        pave_tactile = 'Oui'
        ports_usb = 'Toutes'
        batterie = 100

    db = get_db()
    db.execute('''
        INSERT INTO inventory
            (model_slug, model_name, fan, sn, statut, username, code_user, license_num, obs,
             disque_dur, etat_clavier, systeme_operateur, etat_ecran, batterie, ram, ports_usb, pave_tactile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (model_slug, model_name, fan, sn, statut, username, code_user, license_num, obs,
          disque_dur, etat_clavier, systeme_operateur, etat_ecran, batterie, ram, ports_usb, pave_tactile))
    db.commit()


def update_item(db_id, model_slug, model_name, fan, sn, statut,
                username, code_user, license_num, obs,
                disque_dur=None, etat_clavier=None, systeme_operateur=None,
                etat_ecran=None, batterie=None, ram=None, ports_usb=None,
                pave_tactile=None):
    """Update all information for an existing computer record."""
    if statut in ('Créé', 'Free'):
        disque_dur = 'Oui'
        ram = 'Oui'
        etat_clavier = 'Oui'
        etat_ecran = 'Oui'
        systeme_operateur = 'Oui'
        pave_tactile = 'Oui'
        ports_usb = 'Toutes'
        batterie = 100

    db = get_db()
    db.execute('''
        UPDATE inventory SET
            model_slug = ?,
            model_name = ?,
            fan = ?,
            sn = ?,
            statut = ?,
            username = ?,
            code_user = ?,
            license_num = ?,
            obs = ?,
            disque_dur = ?,
            etat_clavier = ?,
            systeme_operateur = ?,
            etat_ecran = ?,
            batterie = ?,
            ram = ?,
            ports_usb = ?,
            pave_tactile = ?
        WHERE id = ?
    ''', (model_slug, model_name, fan, sn, statut, username, code_user, license_num, obs,
          disque_dur, etat_clavier, systeme_operateur, etat_ecran, batterie, ram, ports_usb, pave_tactile, db_id))
    db.commit()


def bulk_insert_free(model_slug, model_name, statut, quantity, sn=None):
    """Insert `quantity` identical skeleton rows (Free status with functional components)."""
    db = get_db()
    for index in range(quantity):
        db.execute('''
            INSERT INTO inventory
                (model_slug, model_name, fan, sn, statut, username, code_user, license_num, obs,
                 disque_dur, etat_clavier, systeme_operateur, etat_ecran, batterie, ram, ports_usb, pave_tactile)
            VALUES (?, ?, NULL, NULL, ?, NULL, NULL, NULL, NULL,
                    'Oui', 'Oui', 'Oui', 'Oui', 100, 'Oui', 'Toutes', 'Oui')
        ''', (model_slug, model_name, statut))
        if index == 0 and sn:
            db.execute('UPDATE inventory SET sn = ? WHERE id = last_insert_rowid()', (sn,))
    db.commit()


def delete_item_by_id(db_id):
    """Delete one row; returns the model_slug for redirect."""
    db = get_db()
    row = db.execute(
        'SELECT model_slug FROM inventory WHERE id = ?', (db_id,)
    ).fetchone()
    slug = row['model_slug'] if row else None
    db.execute('DELETE FROM inventory WHERE id = ?', (db_id,))
    db.commit()
    return slug


def delete_items_batch(id_list):
    """Delete multiple rows by their IDs; returns list of affected model_slugs."""
    if not id_list:
        return []
    db = get_db()
    placeholders = ', '.join('?' for _ in id_list)
    rows = db.execute(
        f'SELECT DISTINCT model_slug FROM inventory WHERE id IN ({placeholders})',
        id_list
    ).fetchall()
    slugs = [r['model_slug'] for r in rows if r['model_slug']]
    db.execute(f'DELETE FROM inventory WHERE id IN ({placeholders})', id_list)
    db.commit()
    return slugs


# ---------------------------------------------------------------------------
# Component labels & AI preparation engine
# ---------------------------------------------------------------------------

COMPONENT_LABELS = {
    'disque_dur': 'Disque dur',
    'ram': 'La RAM',
    'etat_clavier': 'État du clavier',
    'etat_ecran': 'État de l\'écran',
    'pave_tactile': 'Pavé tactile',
    'systeme_operateur': 'Système opérateur',
    'ports_usb': 'Ports USB',
    'batterie': 'Batterie',
}


def get_compatible_donors(model_slug, target_id):
    """
    Find other computers in 'En stock' with the exact same model_slug, excluding target_id.
    """
    db = get_db()
    rows = db.execute('''
        SELECT * FROM inventory
        WHERE model_slug = ? AND statut = 'En stock' AND id != ?
        ORDER BY id ASC
    ''', (model_slug, target_id)).fetchall()
    return [dict(r) for r in rows]


def execute_component_transfers(target_id, transfers):
    """
    Transfers working components from donor PCs to target PC within an atomic SQLite transaction.
    transfers is a dict: { component_key: donor_id }
    """
    db = get_db()
    cursor = db.cursor()

    target = cursor.execute('SELECT * FROM inventory WHERE id = ?', (target_id,)).fetchone()
    if not target:
        raise ValueError(f"Ordinateur cible ID {target_id} introuvable.")

    target_model_slug = target['model_slug']
    target_ident = target['sn'] or target['fan'] or f"ID-{target['id']}"

    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
    transferred_log = []
    donor_updates = {}

    target_sets = []
    target_params = []

    for comp_key, donor_id in transfers.items():
        if comp_key not in COMPONENT_LABELS:
            continue
        try:
            donor_id = int(donor_id)
        except (ValueError, TypeError):
            continue

        if donor_id == target_id:
            continue

        donor = cursor.execute('SELECT * FROM inventory WHERE id = ?', (donor_id,)).fetchone()
        if not donor:
            raise ValueError(f"Ordinateur donneur ID {donor_id} introuvable.")

        # Safeguard 1: Same PC model
        if donor['model_slug'] != target_model_slug:
            raise ValueError(f"Incompatibilité de modèle entre {donor['model_name']} et {target['model_name']}.")

        # Safeguard 2: Donor component must be working
        donor_val = donor[comp_key]
        if comp_key == 'batterie':
            if donor_val is None or int(donor_val) < 50:
                raise ValueError(f"La batterie du donneur ({donor_val}%) est insuffisante.")
        elif comp_key == 'ports_usb':
            if donor_val != 'Toutes':
                raise ValueError(f"Les ports USB du donneur ({donor_val}) ne sont pas complets.")
        else:
            if donor_val != 'Oui':
                raise ValueError(f"Le composant {COMPONENT_LABELS[comp_key]} du donneur n'est pas fonctionnel.")

        # Determine values to swap
        if comp_key == 'batterie':
            new_target_val = int(donor_val)
            new_donor_val = int(target['batterie']) if target['batterie'] is not None else 0
        elif comp_key == 'ports_usb':
            new_target_val = donor_val
            new_donor_val = 'Non'
        else:
            new_target_val = 'Oui'
            new_donor_val = 'Non'

        target_sets.append(f"{comp_key} = ?")
        target_params.append(new_target_val)

        donor_ident = donor['sn'] or donor['fan'] or f"ID-{donor['id']}"
        comp_label = COMPONENT_LABELS[comp_key]
        transferred_log.append(f"{comp_label} (depuis {donor_ident})")

        if donor_id not in donor_updates:
            donor_updates[donor_id] = {
                'sets': [],
                'params': [],
                'logs': [],
                'donor_row': donor
            }
        donor_updates[donor_id]['sets'].append(f"{comp_key} = ?")
        donor_updates[donor_id]['params'].append(new_donor_val)
        donor_updates[donor_id]['logs'].append(f"{comp_label} transféré vers {target_ident}")

    if not target_sets:
        return {'success': False, 'message': 'Aucun composant valide sélectionné pour le transfert.'}

    # Append provenance in target PC obs
    target_old_obs = target['obs'] or ''
    target_log_entry = f"[{now_str} Préparation IA: {', '.join(transferred_log)}]"
    new_target_obs = f"{target_old_obs}\n{target_log_entry}".strip()
    target_sets.append("obs = ?")
    target_params.append(new_target_obs)
    target_params.append(target_id)

    # 1. Update Target PC
    cursor.execute(f"UPDATE inventory SET {', '.join(target_sets)} WHERE id = ?", tuple(target_params))

    # 2. Update Donor PCs
    for d_id, d_data in donor_updates.items():
        donor_old_obs = d_data['donor_row']['obs'] or ''
        donor_log_entry = f"[{now_str} Prélèvement IA: {', '.join(d_data['logs'])}]"
        new_donor_obs = f"{donor_old_obs}\n{donor_log_entry}".strip()

        d_sets = d_data['sets'] + ["obs = ?"]
        d_params = d_data['params'] + [new_donor_obs, d_id]
        cursor.execute(f"UPDATE inventory SET {', '.join(d_sets)} WHERE id = ?", tuple(d_params))

    db.commit()

    updated_target = dict(cursor.execute('SELECT * FROM inventory WHERE id = ?', (target_id,)).fetchone())
    return {
        'success': True,
        'message': f"PC {target_ident} préparé avec succès.",
        'target': updated_target,
        'transferred_components': transferred_log
    }
