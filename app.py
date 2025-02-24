import os
import logging
from flask import Flask
from database import db, init_db
from extensions import init_extensions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Initialize database
init_db(app)

# Initialize extensions
init_extensions(app, db)

# Import and register blueprints
with app.app_context():
    try:
        # Import blueprints
        from routes.auth import auth
        from routes.main import main
        from routes.service import service
        from routes.billing import billing
        from routes.admin import admin
        from routes.health import health

        # Register blueprints
        blueprints = [
            (auth, '/auth'),
            (main, '/'),
            (service, '/service'),
            (billing, '/billing'),
            (admin, '/admin'),
            (health, '/health')
        ]

        for blueprint, url_prefix in blueprints:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            logger.info(f"Registered blueprint: {blueprint.name}")

        # Create database tables
        db.create_all()
        logger.info("Database tables created")

    except Exception as e:
        logger.error(f"Error during app initialization: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start Flask server: {str(e)}", exc_info=True)
        raise