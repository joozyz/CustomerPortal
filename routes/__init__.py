# Import all routes here for proper package initialization
from flask import Blueprint

# Import route modules
from .billing import billing
from .auth import auth
from .main import main
from .admin import admin
from .service import service

# Export all blueprints
__all__ = ['billing', 'auth', 'main', 'admin', 'service']