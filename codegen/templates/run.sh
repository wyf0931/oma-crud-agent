#!/bin/bash

# Start script for {{ project.name }}

echo "Starting {{ project.name }}..."

# Install dependencies with uv
uv sync

# Initialize database
uv run python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized')"

# Run the application
uv run python -c "
from app import create_app
import webbrowser
import threading
import time

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:5000/admin/')

app = create_app()
threading.Thread(target=open_browser).start()
app.run(host='127.0.0.1', port=5000, debug=True)
"
