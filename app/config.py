"""
Application Configuration
"""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'inventory-secret-key-2024')
    DB_PATH = os.path.join(BASE_DIR, 'inventory.db')
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
