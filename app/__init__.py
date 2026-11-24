"""
Flask Application Factory
"""
from flask import Flask
from .config import Config
from .models.database import close_db, init_db


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(config_class)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = not app.debug
    if not app.debug and not app.config.get('SECRET_KEY'):
        raise RuntimeError('Set SECRET_KEY in the environment before running in production.')
    app.teardown_appcontext(close_db)

    # Initialize database
    with app.app_context():
        init_db()

    # Register blueprints
    from .routes.inventory import inventory_bp
    from .routes.auth import auth_bp, install_request_security
    from .routes.helpdesk import helpdesk_bp
    app.register_blueprint(inventory_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(helpdesk_bp)
    install_request_security(app)

    return app
