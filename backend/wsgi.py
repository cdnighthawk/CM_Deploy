"""WSGI entry for Gunicorn on Render."""
from app import create_app
from app.api._in_app_notifications import register_on_app

app = create_app()
register_on_app(app)
