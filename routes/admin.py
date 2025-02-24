from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User, Service, Container, SystemActivity, SystemAlert
from utils import admin_required
from utils.podman import podman_manager
from datetime import datetime, timedelta
import logging
from app import db # Assuming db is defined in app.py

# Configure logging for admin actions
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__)

@admin.route('/admin')
@admin.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        # Get basic metrics
        users = User.query.all()
        services = Service.query.all()
        containers = Container.query.all()

        # Get recent activities
        recent_activities = SystemActivity.query.order_by(
            SystemActivity.timestamp.desc()
        ).limit(5).all()

        # Get system alerts
        system_alerts = SystemAlert.query.filter(
            SystemAlert.resolved_at.is_(None)
        ).order_by(SystemAlert.timestamp.desc()).all()

        # Generate chart data for the last 7 days
        labels = []
        users_data = []
        services_data = []

        for i in range(7, 0, -1):
            date = datetime.utcnow() - timedelta(days=i)
            labels.append(date.strftime('%Y-%m-%d'))

            # Count active users and services for each day
            users_data.append(User.query.filter(
                User.is_active == True,
                User.created_at <= date
            ).count())

            services_data.append(Container.query.filter(
                Container.status == 'running',
                Container.created_at <= date
            ).count())

        chart_data = {
            'labels': labels,
            'users': users_data,
            'services': services_data
        }

        # Get system metrics
        system_metrics = {
            'total_users': len(users),
            'active_services': len([s for s in services if s.is_active]),
            'total_containers': len(containers),
            'system_health': podman_manager.get_system_health()
        }

        logger.info(f"Admin dashboard accessed by {current_user.username}")
        return render_template('admin/dashboard.html',
                           metrics=system_metrics,
                           recent_activities=recent_activities,
                           system_alerts=system_alerts,
                           chart_data=chart_data)
    except Exception as e:
        logger.error(f"Error accessing admin dashboard: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('admin/dashboard.html', error=True)

@admin.route('/admin/users')
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin.route('/admin/services')
@login_required
@admin_required
def manage_services():
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

@admin.route('/admin/monitoring')
@login_required
@admin_required
def system_monitoring():
    # Get detailed system health information
    health_data = podman_manager.get_detailed_health()
    return render_template('admin/monitoring.html', health_data=health_data)

@admin.route('/admin/backups')
@login_required
@admin_required
def backup_management():
    return render_template('admin/backups.html')

@admin.route('/admin/settings')
@login_required
@admin_required
def settings():
    return render_template('admin/settings.html')

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
            db.session.commit() #Added to save changes
            return redirect(url_for('admin.manage_users'))
        return render_template('admin/manage_user.html', user=user)
    except Exception as e:
        logger.error(f"Error managing user {user_id}: {str(e)}")
        flash('Error managing user', 'error')
        return redirect(url_for('admin.manage_users'))

@admin.route('/admin/services/<int:service_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service(service_id):
    try:
        if service_id == 0:  # New service
            service = Service()
        else:
            service = Service.query.get_or_404(service_id)

        if request.method == 'POST':
            service.name = request.form.get('name')
            service.description = request.form.get('description')
            service.price = float(request.form.get('price'))

            if service_id == 0:
                db.session.add(service)
                logger.info(f"New service {service.name} created by admin {current_user.username}")
                flash('New service has been created', 'success')
            else:
                logger.info(f"Service {service.id} updated by admin {current_user.username}")
                flash('Service has been updated', 'success')

            db.session.commit()
            return redirect(url_for('admin.manage_services'))

        return render_template('admin/manage_service.html', service=service)
    except Exception as e:
        logger.error(f"Error managing service {service_id}: {str(e)}")
        flash('Error managing service', 'error')
        return redirect(url_for('admin.manage_services'))

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