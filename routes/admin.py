from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User, Service, Container
from utils import admin_required
from utils.podman import podman_manager
import logging

# Configure logging for admin actions
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__)

@admin.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        users = User.query.all()
        services = Service.query.all()
        containers = Container.query.all()

        # Get system metrics
        system_metrics = {
            'total_users': len(users),
            'active_services': len([s for s in services if s.is_active]),
            'total_containers': len(containers),
            'system_health': podman_manager.get_system_health()
        }

        logger.info(f"Admin dashboard accessed by {current_user.username}")
        return render_template('admin/dashboard.html', 
                            users=users, 
                            services=services,
                            metrics=system_metrics)
    except Exception as e:
        logger.error(f"Error accessing admin dashboard: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('admin/dashboard.html', error=True)

@admin.route('/admin/podman-status')
@login_required
@admin_required
def podman_status():
    try:
        status, message = podman_manager.check_system()
        logger.info(f"Podman status checked by {current_user.username}: {status}")
        return jsonify({
            'status': 'ok' if status else 'error',
            'message': message
        })
    except Exception as e:
        logger.error(f"Error checking Podman status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to check Podman status'
        }), 500

@admin.route('/admin/users/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'deactivate':
                user.is_active = False
                logger.info(f"User {user.username} deactivated by admin {current_user.username}")
                flash('User has been deactivated', 'success')
            elif action == 'activate':
                user.is_active = True
                logger.info(f"User {user.username} activated by admin {current_user.username}")
                flash('User has been activated', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        return render_template('admin/manage_user.html', user=user)
    except Exception as e:
        logger.error(f"Error managing user {user_id}: {str(e)}")
        flash('Error managing user', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/services/<int:service_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service(service_id):
    try:
        service = Service.query.get_or_404(service_id)
        if request.method == 'POST':
            service.name = request.form.get('name', service.name)
            service.description = request.form.get('description', service.description)
            service.price = float(request.form.get('price', service.price))
            logger.info(f"Service {service.id} updated by admin {current_user.username}")
            flash('Service has been updated', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        return render_template('admin/manage_service.html', service=service)
    except Exception as e:
        logger.error(f"Error managing service {service_id}: {str(e)}")
        flash('Error managing service', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/admin/system-health')
@login_required
@admin_required
def system_health():
    try:
        health_data = podman_manager.get_detailed_health()
        logger.info(f"System health checked by admin {current_user.username}")
        return jsonify(health_data)
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to check system health'
        }), 500