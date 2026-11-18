"""
One-time migration: rebuilds the inventory table to:
  - Drop item_id column
  - Add UNIQUE constraint on fan (NULLs are excluded from uniqueness in SQLite)
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'inventory.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = OFF')
    cur = conn.cursor()

    # Check if already migrated
    cols = [r[1] for r in cur.execute('PRAGMA table_info(inventory)').fetchall()]
    if 'item_id' not in cols:
        print('Already migrated, nothing to do.')
        conn.close()
        return

    print('Starting migration...')

    # 1. Rename old table
    cur.execute('ALTER TABLE inventory RENAME TO inventory_old')

    # 2. Create new table (no item_id, UNIQUE on fan)
    cur.execute('''
        CREATE TABLE inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            model_slug  TEXT,
            model_name  TEXT,
            fan         TEXT UNIQUE,
            sn          TEXT,
            statut      TEXT,
            username    TEXT,
            code_user   TEXT,
            license_num TEXT,
            obs         TEXT
        )
    ''')

    # 3. Copy data (drop item_id, keep rest)
    # For duplicate FANs (if any), only keep the first occurrence (lowest id)
    cur.execute('''
        INSERT INTO inventory (id, model_slug, model_name, fan, sn, statut, username, code_user, license_num, obs)
        SELECT id, model_slug, model_name,
               CASE WHEN fan = '' OR fan IS NULL THEN NULL ELSE fan END,
               sn, statut, username, code_user, license_num, obs
        FROM inventory_old
        WHERE id IN (
            SELECT MIN(id) FROM inventory_old
            GROUP BY CASE WHEN fan = '' OR fan IS NULL THEN CAST(id AS TEXT) ELSE fan END
        )
    ''')

    # 4. Drop old table
    cur.execute('DROP TABLE inventory_old')

    conn.commit()
    conn.close()
    print('Migration complete.')

if __name__ == '__main__':
    migrate()
