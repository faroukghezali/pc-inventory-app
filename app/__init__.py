"""
Flask Application Factory
"""
from flask import Flask
from .config import Config
from .models.database import init_db


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(config_class)

    # Initialize database
    with app.app_context():
        init_db()

    # Register blueprints
    from .routes.inventory import inventory_bp
    app.register_blueprint(inventory_bp)

    return app
