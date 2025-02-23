import os
import logging
from flask import Flask
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

# Create Flask app
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
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Configure rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Initialize database
db.init_app(app)

# Initialize application context and create database tables
with app.app_context():
    # Import models first
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create database tables
    db.create_all()
    logger.info("Database tables created successfully")

    try:
        # Import and register blueprints
        from routes import billing
        app.register_blueprint(billing)
        logger.info("Blueprints registered successfully")
    except Exception as e:
        logger.error(f"Error registering blueprints: {str(e)}")
        raise

    # Import main routes last to avoid circular imports
    import routes