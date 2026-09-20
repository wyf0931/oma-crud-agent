"""Configuration for {{ project.name }}."""

import os
from pathlib import Path

# Get the instance folder
basedir = Path(__file__).parent


class Config:
    """Base configuration."""

    # Secret key
    SECRET_KEY = os.getenv('SECRET_KEY', '{{ project.secret_key }}')

    # Database
    instance_folder = basedir / 'instance'
    instance_folder.mkdir(exist_ok=True)
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{instance_folder}/app.db'

    # Flask-SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Admin
    FLASK_ADMIN_SWATCH = '{{ project.theme }}'

    # Chinese is the default locale for generated internal systems.
    BABEL_DEFAULT_LOCALE = 'zh_CN'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
