import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting Flask server on port 5000...")
        logger.debug("Checking environment variables...")
        # Log critical environment variables (without their values)
        for var in ['DATABASE_URL', 'SESSION_SECRET', 'STRIPE_SECRET_KEY']:
            logger.debug(f"Checking {var}... {'Present' if var in app.config else 'Missing'}")

        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start Flask server: {str(e)}", exc_info=True)
        raise