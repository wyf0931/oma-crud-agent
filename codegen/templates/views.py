"""Flask-Admin views for {{ project.name }}."""

from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView


class UserView(ModelView):
    """Chinese labels for the built-in user model."""
    column_labels = {
        'id': '编号',
        'username': '用户名',
        'password_hash': '密码哈希',
        'created_time': '创建时间',
        'modified_time': '修改时间',
    }


{% for module in modules %}
class {{ module.name }}View(ModelView):
    """Chinese labels for {{ module.label }}."""
    column_labels = {
        'id': '编号',
        'created_time': '创建时间',
        'modified_time': '修改时间',
{% for field in fields[module.name] %}
        '{{ field.name }}': '{{ field.label }}',
{% endfor %}
    }


{% endfor %}
