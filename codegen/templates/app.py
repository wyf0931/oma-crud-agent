"""Flask application factory for {{ project.name }}."""

from flask import Flask, request, session
from flask_babel import Babel
from flask_admin import Admin

from extensions import db
from models import *
from views import *
from config import Config


def get_locale():
    """Use Chinese by default, with an optional explicit language switch."""
    requested = request.args.get('lang')
    if requested in ('zh', 'zh_CN', 'en'):
        session['lang'] = 'zh_CN' if requested in ('zh', 'zh_CN') else 'en'
    return session.get('lang', 'zh_CN')


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    Babel(app, locale_selector=get_locale)

    # Initialize extensions
    db.init_app(app)

    # Create admin interface
    admin = Admin(app, name='{{ project.name }}')

    {% for module in modules %}
    # {{ module.label }}
    from models import {{ module.name }}
    admin.add_view({{ module.name }}View({{ module.name }}, db.session, name='{{ module.label }}'))
    {% endfor %}

    # User management
    from models import User
    admin.add_view(UserView(User, db.session, name='用户管理'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
