import os
import logging
import traceback
from app import app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting Flask server on port 5000...")
        logger.debug("Checking environment variables...")
        required_vars = ['DATABASE_URL', 'SESSION_SECRET']
        for var in required_vars:
            if var in os.environ:
                logger.info(f"{var} is present")
            else:
                logger.error(f"Missing required environment variable: {var}")
                raise ValueError(f"Missing {var}")

        # Print startup message to make it clear in the logs
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