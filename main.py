import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Flask server on port 8080...")
    app.run(host="0.0.0.0", port=8080, debug=True)