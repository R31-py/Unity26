"""Pika hyrëse për gunicorn në prodhim (Render).

Përdorim: gunicorn wsgi:app
"""
import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))
