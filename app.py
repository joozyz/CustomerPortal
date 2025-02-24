import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

# Create Flask app
app = Flask(__name__)

# Required configuration
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    raise ValueError("SESSION_SECRET environment variable is required")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
if not app.config["SQLALCHEMY_DATABASE_URI"]:
    raise ValueError("DATABASE_URL environment variable is required")

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions with app
logger.info("Initializing Flask extensions...")
db.init_app(app)
login_manager.init_app(app)
migrate.init_app(app, db)

# Configure login manager
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Configure rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Health check endpoint
@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({'status': 'ok', 'message': 'Service is healthy'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Import and register blueprints
with app.app_context():
    try:
        logger.info("Starting application initialization...")

        # Import models first to ensure they're registered with SQLAlchemy
        from models import User

        @login_manager.user_loader
        def load_user(user_id):
            try:
                return User.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Import and register blueprints
        logger.info("Importing blueprints...")
        from routes.auth import auth
        from routes.main import main
        from routes.service import service
        from routes.billing import billing
        from routes.admin import admin
        from routes.health import health #Added this line

        logger.info("Registering blueprints...")
        blueprints = [
            (auth, '/auth'),
            (main, '/'),
            (service, '/service'),
            (billing, '/billing'),
            (admin, '/admin'),
            (health, '/health') #Added this line
        ]

        for blueprint, url_prefix in blueprints:
            try:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                logger.info(f"Successfully registered blueprint: {blueprint.name}")
            except Exception as e:
                logger.error(f"Failed to register blueprint {blueprint.name}: {str(e)}")
                raise

        logger.info("All blueprints registered successfully")

        # Create database tables
        db.create_all()
        logger.info("Database tables created successfully")

        logger.info("Application initialization completed successfully")

    except Exception as e:
        logger.error(f"Error during application setup: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting Flask server on port 5000...")
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start Flask server: {str(e)}", exc_info=True)
        raise