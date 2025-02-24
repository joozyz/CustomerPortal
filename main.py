import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    with app.app_context():
        logger.info("Starting Flask server on port 5000...")
        app.run(host="0.0.0.0", port=5000, debug=True)