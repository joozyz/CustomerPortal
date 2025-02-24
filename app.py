import os
import logging
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
limiter = None

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET")

    # Configure SQLAlchemy with PostgreSQL
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
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

    # Configure Login Manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Configure rate limiter
    global limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    # Initialize database
    db.init_app(app)

    # Register blueprints
    from routes.auth import auth
    from routes.service import service
    from routes.main import main
    from routes.admin import admin
    from routes.billing import billing

    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(service, url_prefix='/service')
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(billing, url_prefix='/billing')

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

    return app

# Create the application instance
app = create_app()

# Initialize application context and create database tables
with app.app_context():
    # Import models first
    from models import User, Service, Container, CustomerProfile, BillingInfo, SystemActivity

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create database tables
    db.create_all()
    logger.info("Database tables created successfully")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)