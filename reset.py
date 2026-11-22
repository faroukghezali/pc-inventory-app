"""Create the first administrator or securely reset an existing admin password.

Run from the project directory with: python reset.py [admin_username]
The password is read interactively and is never accepted on the command line.
"""
import argparse
import getpass
import hashlib
import hmac
import secrets
import sqlite3

try:
    from werkzeug.security import generate_password_hash  # type: ignore[import-not-found]
except ModuleNotFoundError:
    def generate_password_hash(password):
        """Create a Werkzeug-compatible PBKDF2-SHA256 password hash."""
        iterations = 600_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            'sha256', password.encode('utf-8'), salt.encode('ascii'), iterations
        ).hex()
        return f'pbkdf2:sha256:{iterations}${salt}${digest}'

from app.config import Config


def main():
    parser = argparse.ArgumentParser(description='Create or reset an IT Inventory administrator.')
    parser.add_argument('username', nargs='?', help='Administrator username (prompted if omitted)')
    username = (parser.parse_args().username or input('Administrator username: ')).strip()
    if len(username) < 3 or len(username) > 80 or not username.replace('_', '').replace('-', '').isalnum():
        parser.error('Username must be 3–80 characters using letters, numbers, hyphens, or underscores.')

    password = getpass.getpass('New administrator password (minimum 12 characters): ')
    confirmation = getpass.getpass('Confirm password: ')
    if len(password) < 12:
        parser.error('Password must contain at least 12 characters.')
    if password != confirmation:
        parser.error('Passwords do not match.')

    connection = sqlite3.connect(Config.DB_PATH)
    try:
        connection.execute('''
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                access_level TEXT NOT NULL CHECK(access_level IN ('read', 'write', 'full')),
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        existing = connection.execute(
            'SELECT id, is_admin FROM app_users WHERE username = ? COLLATE NOCASE', (username,)
        ).fetchone()
        if existing and not existing[1]:
            parser.error('That username belongs to a non-admin account. Choose a separate administrator username.')
        if existing:
            connection.execute(
                "UPDATE app_users SET password_hash = ?, access_level = 'full' WHERE id = ?",
                (generate_password_hash(password), existing[0]),
            )
            action = 'reset'
        else:
            connection.execute(
                "INSERT INTO app_users (username, password_hash, access_level, is_admin) VALUES (?, ?, 'full', 1)",
                (username, generate_password_hash(password)),
            )
            action = 'created'
        connection.commit()
        print(f'Administrator {username!r} {action} successfully.')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
