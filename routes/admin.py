from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User, Service, Container, SystemActivity, SystemAlert
from routes.auth import admin_required
from utils.podman import podman_manager
from datetime import datetime, timedelta
import logging
from app import db

# Configure logging for admin actions
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__, 
                 template_folder='../templates/admin')

@admin.route('/')
@admin.route('/dashboard')
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

            users_data.append(User.query.filter(
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
            'active_services': len([s for s in services if getattr(s, 'is_active', True)]),
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
        flash('Error loading dashboard data', 'danger')
        return render_template('admin/dashboard.html', error=True)

@admin.route('/users')
@login_required
@admin_required
def manage_users():
    try:
        users = User.query.all()
        return render_template('admin/users.html', users=users)
    except Exception as e:
        logger.error(f"Error managing users: {str(e)}")
        flash('Error loading user data', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/services')
@login_required
@admin_required
def manage_services():
    try:
        services = Service.query.all()
        return render_template('admin/services.html', services=services)
    except Exception as e:
        logger.error(f"Error managing services: {str(e)}")
        flash('Error loading service data', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/monitoring')
@login_required
@admin_required
def system_monitoring():
    try:
        health_data = podman_manager.get_detailed_health()
        return render_template('admin/monitoring.html', health_data=health_data)
    except Exception as e:
        logger.error(f"Error accessing monitoring: {str(e)}")
        flash('Error loading monitoring data', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/backups')
@login_required
@admin_required
def backup_management():
    try:
        return render_template('admin/backups.html')
    except Exception as e:
        logger.error(f"Error accessing backup management: {str(e)}")
        flash('Error loading backup data', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/settings')
@login_required
@admin_required
def settings():
    try:
        return render_template('admin/settings.html')
    except Exception as e:
        logger.error(f"Error accessing settings: {str(e)}")
        flash('Error loading settings', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/podman-status')
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

@admin.route('/users/<int:user_id>', methods=['GET', 'POST'])
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
            db.session.commit()
            return redirect(url_for('admin.manage_users'))
        return render_template('admin/manage_user.html', user=user)
    except Exception as e:
        logger.error(f"Error managing user {user_id}: {str(e)}")
        flash('Error managing user', 'danger')
        return redirect(url_for('admin.manage_users'))

@admin.route('/system-health')
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