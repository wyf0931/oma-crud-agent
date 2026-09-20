# {{ project.name }}

{{ project.version }}

## Description

{{ project.name }} is a Flask-Admin based CRUD management system.

## Installation

1. Install [uv](https://github.com/astral-sh/uv):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv sync
```

## Usage

Start the application:
```bash
./run.sh
```

Or manually:
```bash
uv run python -c "from app import app, db; app.app_context().push(); db.create_all()"
uv run python -c "from app import create_app; app = create_app(); app.run()"
```

## Access

- URL: http://localhost:5000/admin/
- Username: {{ project.admin_account }}
- Password: {{ project.admin_password }}

## Modules

{% for module in modules %}
- {{ module.label }} ({{ module.name }}): {{ module.description }}
{% endfor %}

## Configuration

Configuration files:
- `config.py`: Application configuration
- `.env`: Environment variables (copy from `.env.example`)

## License

MIT License
