from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import Service, Container, Subscription
import logging
import os

service = Blueprint('service', __name__)
logger = logging.getLogger(__name__)

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

        return render_template('dashboard.html',
                             stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'),
                             current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard. Please try again.', 'danger')
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