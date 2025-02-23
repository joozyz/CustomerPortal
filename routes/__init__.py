# Import all routes here for proper package initialization
from flask import Blueprint
from app import app

# Import route modules
from .billing import billing
from .auth import auth
from .main import main
from .admin import admin
from .service import service

# Register blueprints
app.register_blueprint(billing, url_prefix='/billing')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(main)
app.register_blueprint(admin, url_prefix='/admin')
app.register_blueprint(service, url_prefix='/service')

# Export all blueprints
__all__ = ['billing', 'auth', 'main', 'admin', 'service']