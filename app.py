import os
import logging
import traceback
from flask import Flask, jsonify
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

# Verify required environment variables
required_vars = ['DATABASE_URL', 'SESSION_SECRET']
for var in required_vars:
    if var not in os.environ:
        logger.error(f"Missing required environment variable: {var}")
        raise ValueError(f"Missing {var}")
    else:
        logger.info(f"Found environment variable: {var}")

app.secret_key = os.environ.get("SESSION_SECRET")

try:
    logger.info("Initializing database...")
    init_db(app)
    logger.info("Database initialized successfully")

    logger.info("Initializing extensions...")
    init_extensions(app, db)
    logger.info("Extensions initialized successfully")

    # Import and register blueprints
    with app.app_context():
        logger.info("Starting blueprint registration...")

        try:
            logger.info("Importing auth blueprint...")
            from routes.auth import auth
            app.register_blueprint(auth, url_prefix='/auth')
            logger.info("Auth blueprint registered successfully")

            logger.info("Importing main blueprint...")
            from routes.main import main
            app.register_blueprint(main, url_prefix='/')
            logger.info("Main blueprint registered successfully")

            logger.info("Importing service blueprint...")
            from routes.service import service
            app.register_blueprint(service, url_prefix='/service')
            logger.info("Service blueprint registered successfully")

            logger.info("Importing billing blueprint...")
            from routes.billing import billing
            app.register_blueprint(billing, url_prefix='/billing')
            logger.info("Billing blueprint registered successfully")

            logger.info("Importing health blueprint...")
            from routes.health import health
            app.register_blueprint(health, url_prefix='/health')
            logger.info("Health blueprint registered successfully")

            # Import admin last to avoid circular dependencies
            logger.info("Importing admin blueprint...")
            from routes.admin import admin
            app.register_blueprint(admin, url_prefix='/admin')
            logger.info("Admin blueprint registered successfully")

            logger.info("All blueprints registered successfully")

            # Create database tables
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Error during blueprint registration: {str(e)}")
            logger.error(traceback.format_exc())
            raise

except Exception as e:
    logger.error("Error during app initialization:")
    logger.error(traceback.format_exc())
    raise

@app.route('/health')
def health_check():
    """Basic health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        logger.info("Health check endpoint accessed - Database connection successful")
        return jsonify({'status': 'ok', 'message': 'Service is healthy'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # ALWAYS serve the app on port 5000
    try:
        print("=== Starting Flask Application ===")
        print("Server will be available at http://0.0.0.0:5000")
        print("Health check endpoint: http://0.0.0.0:5000/health")
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error("Failed to start Flask server:")
        logger.error(traceback.format_exc())
        print("=== Server Failed to Start ===")
        print(f"Error: {str(e)}")
        raise