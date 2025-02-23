from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, send_file
from flask_login import login_required, current_user
from app import db
from models import Service, Container, Subscription
from utils.podman import podman_manager
from utils.backup_manager import backup_manager
from datetime import datetime
import logging
import os

service = Blueprint('service', __name__)
logger = logging.getLogger(__name__)

@service.route('/services/wordpress/deploy', methods=['POST'])
@login_required
def deploy_wordpress():
    """Deploy a new WordPress instance"""
    try:
        # Get WordPress service
        wordpress_service = Service.query.filter_by(name='WordPress').first()
        if not wordpress_service:
            flash('WordPress service is not available', 'danger')
            return redirect(url_for('service.service_catalog'))

        # Check if user already has an active WordPress instance
        existing_container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=wordpress_service.id,
            status='running'
        ).first()

        if existing_container:
            flash('You already have an active WordPress instance', 'warning')
            return redirect(url_for('service.dashboard'))

        # Deploy WordPress using Podman
        container = podman_manager.deploy_wordpress(
            service=wordpress_service,
            user_id=current_user.id
        )

        if container:
            try:
                db.session.add(container)
                db.session.commit()
                flash('WordPress deployed successfully! You can access it from your dashboard.', 'success')
            except Exception as e:
                logger.error(f"Failed to save WordPress container to database: {str(e)}")
                podman_manager.cleanup_wordpress(container.name)
                flash('Failed to deploy WordPress. Please try again later.', 'danger')
        else:
            flash('Failed to deploy WordPress. Please try again later.', 'danger')

        return redirect(url_for('service.dashboard'))

    except Exception as e:
        logger.error(f"Error in WordPress deployment: {str(e)}")
        flash('An error occurred while deploying WordPress', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/backup', methods=['POST'])
@login_required
def create_backup(service_id):
    """Create a backup for a service"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id,
            status='running'
        ).first()

        if not container:
            flash('No active container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        # Create backup
        success, message = backup_manager.create_backup(service, container)

        if success:
            flash('Backup created successfully', 'success')
            db.session.commit()  # Save the updated last_backup_at timestamp
        else:
            flash(f'Backup failed: {message}', 'danger')

        return redirect(url_for('service.dashboard'))

    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        flash('An error occurred while creating the backup', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/domain', methods=['POST'])
@login_required
def update_domain(service_id):
    """Update domain settings for a service"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            flash('No container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        domain = request.form.get('domain')
        enable_ssl = request.form.get('enable_ssl', 'false') == 'true'

        if domain:
            service.domain = domain
            service.domain_status = 'pending'
            if enable_ssl:
                service.ssl_enabled = True
                # SSL setup would be handled by a background task

            db.session.commit()
            flash('Domain settings updated successfully', 'success')
        else:
            flash('Domain name is required', 'danger')

        return redirect(url_for('service.dashboard'))

    except Exception as e:
        logger.error(f"Error updating domain settings: {str(e)}")
        flash('An error occurred while updating domain settings', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.is_admin:
            return redirect(url_for('admin.admin_dashboard'))

        # Get user's active services and containers
        active_subscriptions = Subscription.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).all()

        active_containers = Container.query.filter_by(
            user_id=current_user.id
        ).all()

        # Get services with their latest backup info
        services = Service.query.join(Container).filter(
            Container.user_id == current_user.id
        ).all()

        return render_template('dashboard.html',
                             services=services,
                             active_subscriptions=active_subscriptions,
                             active_containers=active_containers,
                             stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'))
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('main.index'))

@service.route('/services/catalog')
def service_catalog():
    services = Service.query.all()
    return render_template('services/catalog.html', services=services)

@service.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    service = Service.query.get_or_404(service_id)

    # Check Podman system status
    podman_status, status_message = podman_manager.check_system()
    if not podman_status:
        flash(f'Cannot deploy service: {status_message}', 'danger')
        return redirect(url_for('service.service_catalog'))

    if not service.container_image or not service.container_port:
        flash('This service does not support container deployment', 'danger')
        return redirect(url_for('service.service_catalog'))

    # Check if service is already deployed for this user
    existing_container = Container.query.filter_by(
        user_id=current_user.id,
        service_id=service_id,
        status='running'
    ).first()

    if existing_container:
        flash('Service is already deployed', 'warning')
        return redirect(url_for('service.service_catalog'))

    # Deploy the service using Podman with resource quotas
    container = podman_manager.deploy_service(
        service=service,
        user_id=current_user.id,
        environment=service.environment_vars
    )

    if container:
        try:
            db.session.add(container)
            db.session.commit()
            flash('Service deployed successfully! You can view it in your dashboard.', 'success')
        except Exception as e:
            logging.error(f"Failed to save container to database: {str(e)}")
            flash('Service deployed but failed to save details. Please contact support.', 'warning')
    else:
        flash('Failed to deploy service. Please try again later.', 'danger')

    return redirect(url_for('service.service_catalog'))

@service.route('/containers/<int:container_id>/status')
@login_required
def container_status(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Get detailed container status including resource usage
    status = podman_manager.get_container_status(container.container_id)

    # Update container metrics in database
    if isinstance(status, dict):
        try:
            container.status = status.get('status', 'unknown')
            container.cpu_usage = status.get('cpu_usage', 0.0)
            container.memory_usage = status.get('memory_usage', 0)
            container.last_monitored = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            logging.error(f"Failed to update container metrics: {str(e)}")

    return jsonify(status)

@service.route('/containers/<int:container_id>/stop', methods=['POST'])
@login_required
def stop_container(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('service.dashboard'))

    if podman_manager.stop_container(container.container_id):
        container.status = 'stopped'
        db.session.commit()
        flash('Container stopped successfully', 'success')
    else:
        flash('Failed to stop container', 'danger')

    return redirect(url_for('service.dashboard'))

@service.route('/containers/<int:container_id>/remove', methods=['POST'])
@login_required
def remove_container(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('service.dashboard'))

    if podman_manager.remove_container(container.container_id):
        db.session.delete(container)
        db.session.commit()
        flash('Container removed successfully', 'success')
    else:
        flash('Failed to remove container', 'danger')

    return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/backups', methods=['GET'])
@login_required
def list_backups(service_id):
    """List all backups for a service"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            flash('No container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        backups = backup_manager.list_backups(service)
        return render_template('services/backups.html', 
                             service=service,
                             backups=backups)

    except Exception as e:
        logger.error(f"Error listing backups: {str(e)}")
        flash('An error occurred while listing backups', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/restore/<path:backup_file>', methods=['POST'])
@login_required
def restore_backup(service_id, backup_file):
    """Restore a backup for a service"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id,
            status='running'
        ).first()

        if not container:
            flash('No active container found for this service', 'danger')
            return redirect(url_for('service.backups', service_id=service_id))

        success, message = backup_manager.restore_backup(service, container, backup_file)

        if success:
            flash('Backup restored successfully', 'success')
        else:
            flash(f'Failed to restore backup: {message}', 'danger')

        return redirect(url_for('service.backups', service_id=service_id))

    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}")
        flash('An error occurred while restoring the backup', 'danger')
        return redirect(url_for('service.backups', service_id=service_id))

@service.route('/services/<int:service_id>/backup/settings', methods=['POST'])
@login_required
def update_backup_settings(service_id):
    """Update backup settings for a service"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            flash('No container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        # Update backup settings
        service.backup_enabled = request.form.get('backup_enabled') == 'on'
        service.backup_frequency = request.form.get('backup_frequency', 'daily')
        retention_days = request.form.get('retention_days')
        if retention_days and retention_days.isdigit():
            service.backup_retention_days = int(retention_days)

        db.session.commit()
        flash('Backup settings updated successfully', 'success')

        return redirect(url_for('service.list_backups', service_id=service_id))

    except Exception as e:
        logger.error(f"Error updating backup settings: {str(e)}")
        flash('An error occurred while updating backup settings', 'danger')
        return redirect(url_for('service.list_backups', service_id=service_id))

@service.route('/services/<int:service_id>/backup/download/<path:backup_file>')
@login_required
def download_backup(service_id, backup_file):
    """Download a backup file"""
    try:
        service = Service.query.get_or_404(service_id)

        # Ensure the service belongs to the current user
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            flash('No container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        backup_path = os.path.join(backup_manager.backup_base_path, str(service_id), backup_file)

        if not os.path.exists(backup_path):
            flash('Backup file not found', 'danger')
            return redirect(url_for('service.list_backups', service_id=service_id))

        return send_file(
            backup_path,
            as_attachment=True,
            download_name=f"{service.name}_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.tar.gz"
        )

    except Exception as e:
        logger.error(f"Error downloading backup: {str(e)}")
        flash('An error occurred while downloading the backup', 'danger')
        return redirect(url_for('service.list_backups', service_id=service_id))