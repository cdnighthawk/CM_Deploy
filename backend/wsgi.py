"""WSGI entry for Gunicorn on Render."""
from app import create_app
from werkzeug.middleware.proxy_fix import ProxyFix

app = create_app()

if __import__("os").environ.get("FLASK_ENV", "").strip().lower() == "production":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
