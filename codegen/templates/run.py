#!/usr/bin/env python3
"""Run script for {{ project.name }}."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    args = parser.parse_args()

    app = create_app()

    if args.init_db:
        with app.app_context():
            db.create_all()
            print('Database initialized!')
        sys.exit(0)

    app.run(host='127.0.0.1', port=args.port, debug=False)
