"""
Application entry point.
Run:  python main.py
"""
import os

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig

config = ProductionConfig if os.environ.get('APP_ENV', '').lower() == 'production' else DevelopmentConfig
app = create_app(config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
