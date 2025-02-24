# Import all routes here for proper package initialization
from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# Export all blueprints
__all__ = ['billing', 'auth', 'main', 'admin', 'service']

#Import route modules - moved here to handle potential errors separately
try:
    from .billing import billing
    from .auth import auth
    from .main import main
    from .service import service
    # Import admin last to avoid circular dependencies
    from .admin import admin
except ImportError as e:
    logger.error(f"Error importing route modules: {e}", exc_info=True)
    raise