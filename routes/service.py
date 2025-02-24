from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_login import login_required, current_user
from app import db
from models import Service, Container, SystemActivity
from utils.backup_manager import backup_manager
from utils.podman import podman_manager
from datetime import datetime
import logging
import os

# Initialize blueprint and logger
service = Blueprint('service', __name__)
logger = logging.getLogger(__name__)

@service.route('/dashboard')
@login_required
def dashboard():
    """Display user's service dashboard"""
    try:
        # Get user's active services with their containers
        services = Service.query.join(Container).filter(
            Container.user_id == current_user.id
        ).all()
        logger.debug(f"Found {len(services)} services for user {current_user.id}")

        return render_template('dashboard.html',
                            services=services,
                            current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('main.index'))

@service.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    """Deploy a new service container"""
    try:
        service = Service.query.get_or_404(service_id)

        # Check if container already exists
        existing_container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id,
            status='running'
        ).first()

        if existing_container:
            flash('Service is already deployed', 'warning')
            return redirect(url_for('service.dashboard'))

        # Create new container
        container_name = f"{service.name.lower()}-{current_user.id}"
        container = podman_manager.create_container(
            name=container_name,
            image=service.container_image,
            environment=service.environment_vars
        )

        # Save container info
        new_container = Container(
            container_id=container['Id'],
            name=container_name,
            status='running',
            user_id=current_user.id,
            service_id=service_id,
            port=service.container_port
        )
        db.session.add(new_container)
        db.session.commit()

        flash('Service deployed successfully', 'success')
        return redirect(url_for('service.dashboard'))

    except Exception as e:
        logger.error(f"Error deploying service: {str(e)}")
        flash('Failed to deploy service', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/domain', methods=['POST'])
@login_required
def update_domain(service_id):
    """Update domain configuration for a service"""
    try:
        service = Service.query.get_or_404(service_id)
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            flash('No container found for this service', 'danger')
            return redirect(url_for('service.dashboard'))

        domain = request.form.get('domain')
        enable_ssl = request.form.get('enable_ssl') == 'on'

        service.domain = domain
        service.ssl_enabled = enable_ssl
        service.domain_status = 'pending'

        # Log the activity
        SystemActivity.log_activity(
            action="domain_update",
            description=f"Domain updated to {domain} for service {service.name}",
            user=current_user
        )

        db.session.commit()
        flash('Domain settings updated successfully', 'success')
        return redirect(url_for('service.dashboard'))

    except Exception as e:
        logger.error(f"Error updating domain: {str(e)}")
        flash('Failed to update domain settings', 'danger')
        return redirect(url_for('service.dashboard'))

@service.route('/services/<int:service_id>/status')
@login_required
def get_service_status(service_id):
    """Get current status of a service"""
    try:
        container = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id
        ).first()

        if not container:
            return jsonify({'status': 'not_deployed'})

        status = podman_manager.get_container_status(container.container_id)
        return jsonify({'status': status})

    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        return jsonify({'status': 'error'})

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

@service.route('/services/<int:service_id>/backup/settings', methods=['POST'])
@login_required
def update_backup_settings(service_id):
    """Update backup settings for a service"""
    try:
        service = Service.query.get_or_404(service_id)
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
@service.route('/catalog')
def service_catalog():
    """Display available services"""
    try:
        logger.debug("Fetching services for catalog")
        services = Service.query.all()
        logger.debug(f"Found {len(services)} services")

        return render_template(
            'services/catalog.html',
            services=services,
            current_user=current_user
        )
    except Exception as e:
        logger.error(f"Error loading service catalog: {str(e)}")
        flash('An error occurred while loading the service catalog', 'danger')
        return redirect(url_for('main.index'))