from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import User, Service, Container, SystemActivity, SystemAlert, SystemSettings
from utils import admin_required
from utils.podman import podman_manager
import logging
import json
import psutil
from app import db
from forms import SMTPSettingsForm

# Configure logging for admin actions
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__, 
                 template_folder='../templates/admin',
                 url_prefix='/admin')

@admin.before_request
def check_admin():
    """Check if user is authenticated and is an admin"""
    if not current_user.is_authenticated:
        logger.warning("Unauthenticated user attempted to access admin area")
        flash('Please log in first.', 'warning')
        return redirect(url_for('auth.login'))
    if not current_user.is_admin:
        logger.warning(f"Non-admin user {current_user.username} attempted to access admin area")
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('main.index'))

@admin.route('/health/dashboard')
@login_required
@admin_required
def health_dashboard():
    """Render the health monitoring dashboard"""
    try:
        logger.info(f"Admin {current_user.username} accessing health dashboard")
        return render_template('admin/health_dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering health dashboard: {str(e)}", exc_info=True)
        flash('Error loading health dashboard', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@admin.route('/health/metrics')
@login_required
@admin_required
def health_metrics():
    """Get current health metrics"""
    try:
        logger.info("Collecting health metrics...")
        # Get basic system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        # Calculate uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        # Get disk and network info
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()

        metrics = {
            'status': 'ok',
            'cpu': cpu_percent,
            'memory': memory.percent,
            'uptime': str(timedelta(seconds=int(uptime.total_seconds()))),
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv
            }
        }

        logger.debug(f"Health metrics collected successfully: {json.dumps(metrics)}")
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting health metrics: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin.route('/')
@admin.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        metrics = get_system_metrics()
        branding = {
            'default_theme': request.cookies.get('theme', 'light'),
            'brand_color': request.cookies.get('brandColor', '#007AFF'),
            'brand_name': request.cookies.get('brandName', 'Cloud Services')
        }
        return render_template('admin/dashboard.html',
                           metrics=metrics,
                           recent_activities=get_recent_activities(),
                           system_alerts=get_system_alerts(),
                           chart_data=get_chart_data(),
                           **branding)
    except Exception as e:
        logger.error(f"Error accessing admin dashboard: {str(e)}")
        flash('Error loading dashboard data. Please try again.', 'danger')
        return render_template('admin/dashboard.html', 
                             error=True,
                             metrics=get_empty_metrics(),
                             **get_default_branding())

@admin.route('/branding', methods=['POST'])
@login_required
@admin_required
def update_branding():
    try:
        theme = request.form.get('defaultTheme', 'light')
        brand_color = request.form.get('brandColor', '#007AFF')
        brand_name = request.form.get('brandName', 'Cloud Services')

        response = jsonify({'success': True})

        # Set cookies for branding settings
        response.set_cookie('theme', theme, max_age=31536000)  # 1 year
        response.set_cookie('brandColor', brand_color, max_age=31536000)
        response.set_cookie('brandName', brand_name, max_age=31536000)

        # Log the branding update
        logger.info(f"Branding updated by admin {current_user.username}")
        SystemActivity.log_activity(
            action="branding_update",
            description=f"Updated branding settings",
            user=current_user
        )

        return response
    except Exception as e:
        logger.error(f"Error updating branding: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper functions
def get_system_metrics():
    return {
        'total_users': User.query.count(),
        'active_services': Service.query.filter_by(is_active=True).count(),
        'total_containers': Container.query.count(),
        'system_health': podman_manager.get_system_health()
    }

def get_empty_metrics():
    return {
        'total_users': 0,
        'active_services': 0,
        'total_containers': 0,
        'system_health': 'error'
    }

def get_default_branding():
    return {
        'default_theme': 'light',
        'brand_color': '#007AFF',
        'brand_name': 'Cloud Services'
    }

def get_recent_activities():
    try:
        return SystemActivity.query.order_by(
            SystemActivity.timestamp.desc()
        ).limit(5).all()
    except Exception:
        return []

def get_system_alerts():
    try:
        return SystemAlert.query.filter(
            SystemAlert.resolved_at.is_(None)
        ).order_by(SystemAlert.timestamp.desc()).all()
    except Exception:
        return []

def get_chart_data():
    try:
        labels = []
        users_data = []
        services_data = []

        for i in range(7, 0, -1):
            date = datetime.utcnow() - timedelta(days=i)
            labels.append(date.strftime('%Y-%m-%d'))

            users_count = User.query.filter(
                User.created_at <= date
            ).count()
            users_data.append(users_count)

            services_count = Container.query.filter(
                Container.status == 'running',
                Container.created_at <= date
            ).count()
            services_data.append(services_count)

        return {
            'labels': labels,
            'users': users_data,
            'services': services_data
        }
    except Exception:
        return {'labels': [], 'users': [], 'services': []}

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

@admin.route('/settings/smtp', methods=['GET', 'POST'])
@login_required
@admin_required
def smtp_settings():
    form = SMTPSettingsForm()

    if form.validate_on_submit():
        try:
            # Save SMTP settings
            SystemSettings.set_setting('SMTP_SERVER', form.smtp_server.data, 
                                    'SMTP server hostname', False)
            SystemSettings.set_setting('SMTP_PORT', form.smtp_port.data, 
                                    'SMTP server port', False)
            SystemSettings.set_setting('SMTP_USERNAME', form.smtp_username.data, 
                                    'SMTP username/email', False)
            SystemSettings.set_setting('SMTP_PASSWORD', form.smtp_password.data, 
                                    'SMTP password/app password', True)

            flash('SMTP settings updated successfully.', 'success')
            logger.info(f"SMTP settings updated by admin {current_user.username}")
            return redirect(url_for('admin.settings'))
        except Exception as e:
            logger.error(f"Error saving SMTP settings: {str(e)}")
            flash('Error saving SMTP settings.', 'danger')
            return redirect(url_for('admin.smtp_settings'))

    # Pre-fill form with existing settings
    if request.method == 'GET':
        form.smtp_server.data = SystemSettings.get_setting('SMTP_SERVER', 'smtp.gmail.com')
        form.smtp_port.data = SystemSettings.get_setting('SMTP_PORT', '587')
        form.smtp_username.data = SystemSettings.get_setting('SMTP_USERNAME', '')
        # Don't pre-fill password for security

    return render_template('admin/smtp_settings.html', form=form)