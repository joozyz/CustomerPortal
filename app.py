import os
import logging
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

try:
    # Create Flask app
    app = Flask(__name__)

    # Check and set required environment variables
    session_secret = os.environ.get("SESSION_SECRET")
    if not session_secret:
        logger.error("SESSION_SECRET environment variable is not set")
        raise ValueError("SESSION_SECRET environment variable is required")
    app.secret_key = session_secret

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        raise ValueError("DATABASE_URL environment variable is required")

    # Configure SQLAlchemy with PostgreSQL
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Configure Stripe
    stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not stripe_secret_key:
        logger.warning("STRIPE_SECRET_KEY not found in environment variables")

    app.config["STRIPE_SECRET_KEY"] = stripe_secret_key
    app.config["STRIPE_PUBLISHABLE_KEY"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_your_key")

    # Add request logging
    @app.before_request
    def log_request_info():
        logger.debug('Request Headers: %s', dict(request.headers))
        logger.debug('Request URL: %s', request.url)

    # Health check endpoint
    @app.route('/health')
    def health_check():
        logger.info('Health check endpoint called')
        return 'OK', 200

    # Initialize extensions with app
    logger.info("Initializing Flask extensions...")
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Configure rate limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    # Initialize application context and create database tables
    with app.app_context():
        # Import models first
        from models import User

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        try:
            # Import routes package which will register all blueprints
            logger.info("Importing and registering blueprints...")
            import routes
            logger.info("Routes package imported successfully")
        except Exception as e:
            logger.error(f"Error importing routes: {str(e)}", exc_info=True)
            raise

except Exception as e:
    logger.error(f"Error initializing Flask application: {str(e)}", exc_info=True)
    raise