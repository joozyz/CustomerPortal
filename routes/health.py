from flask import Blueprint, render_template, Response
import psutil
import json
import logging

logger = logging.getLogger(__name__)
health = Blueprint('health', __name__)

@health.route('/status')
def status():
    """Simple health check endpoint"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        return json.dumps({
            'status': 'ok',
            'cpu': cpu_percent,
            'memory': memory.percent
        }), 200
    except Exception as e:
        logger.error(f"Error in status endpoint: {str(e)}", exc_info=True)
        return json.dumps({'status': 'error'}), 500

@health.route('/dashboard')
def dashboard():
    """Render the basic health dashboard"""
    try:
        return render_template('admin/health_dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}", exc_info=True)
        return "Error loading dashboard", 500