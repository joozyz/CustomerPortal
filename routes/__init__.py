# Import all routes here for proper package initialization
from flask import Blueprint
from app import app
import logging

logger = logging.getLogger(__name__)

try:
    # Import route modules
    logger.info("Importing route modules...")
    from .billing import billing
    from .auth import auth
    from .main import main
    from .admin import admin
    from .service import service
    from .health import health

    # Register blueprints
    logger.info("Registering blueprints...")
    app.register_blueprint(billing, url_prefix='/billing')
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(service, url_prefix='/service')
    app.register_blueprint(health, url_prefix='/admin/health')

    # Export all blueprints
    __all__ = ['billing', 'auth', 'main', 'admin', 'service', 'health']

    logger.info("All blueprints registered successfully")
except Exception as e:
    logger.error(f"Error registering blueprints: {str(e)}", exc_info=True)
    raise