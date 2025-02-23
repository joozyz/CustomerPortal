from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from app import db
from models import Service, Container
from utils.backup_manager import backup_manager
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
                             services=services)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('main.index'))

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