# Authentication and access setup

## Create or reset the administrator

Run this from the project directory. The password is entered with hidden terminal input and is never passed as a command-line argument:

```powershell
python reset.py admin
```

Use a unique administrator username with a password of at least 12 characters. Running the command again resets that administrator's password. The password is stored as a one-way Werkzeug password hash in `inventory.db`.

## Run locally

```powershell
python main.py
```

The application redirects unauthenticated visitors to the login page. A successful login session uses an HTTP-only, SameSite cookie and all form submissions are checked for CSRF tokens.

## Production

Set a long random `SECRET_KEY` in the process environment and keep it outside the repository. Then run with production settings:

```powershell
$env:SECRET_KEY = '<secret stored in your deployment secret manager>'
$env:APP_ENV = 'production'
python main.py
```

Production startup fails when `SECRET_KEY` is missing, and session cookies are marked Secure. Serve the app over HTTPS behind a production WSGI server.

## Access levels

- **Read-only:** view inventory and exports; cannot submit changes.
- **Read and Write:** add and edit records; cannot delete records.
- **Full Access:** add, edit, and delete records.
- The administrator can also manage user accounts and permissions.

Activity entries are appended to `src/activity.log` with UTC timestamp, username, HTTP action, route, and response status. Passwords and form contents are never written to this log.
