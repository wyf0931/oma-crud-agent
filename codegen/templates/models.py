"""SQLAlchemy models for {{ project.name }}."""

from extensions import db
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model):
    """User model for authentication."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_time = db.Column(db.DateTime, default=datetime.utcnow)
    modified_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)


{% for module in modules %}
class {{ module.name }}(db.Model):
    """{{ module.description }}"""
    __tablename__ = '{{ module.name.lower() }}s'

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime, default=datetime.utcnow)
    modified_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    {% for field in fields[module.name] %}
    {{ field.name }} = db.Column(
        db.{{ field.type }}{% if field.required %}, nullable=False{% endif %},
        {% if field.can_search %}index=True{% endif %}
    )
    {% endfor %}

{% endfor %}
