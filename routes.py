from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import app, db, limiter
from models import Service, Container
from utils import admin_required, podman_manager
import logging

@app.route('/')
def index():
    services = Service.query.all()
    return render_template('index.html', services=services)

@app.route('/services/catalog')
def service_catalog():
    services = Service.query.all()
    return render_template('services/catalog.html', services=services)

@app.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    service = Service.query.get_or_404(service_id)

    # Check Podman system status
    podman_status, status_message = podman_manager.check_system()
    if not podman_status:
        flash(f'Cannot deploy service: {status_message}', 'danger')
        return redirect(url_for('service_catalog'))

    if not service.container_image or not service.container_port:
        flash('This service does not support container deployment', 'danger')
        return redirect(url_for('service_catalog'))

    # Check if service is already deployed for this user
    existing_container = Container.query.filter_by(
        user_id=current_user.id,
        service_id=service_id,
        status='running'
    ).first()

    if existing_container:
        flash('Service is already deployed', 'warning')
        return redirect(url_for('service_catalog'))

    # Deploy the service using Podman
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

    return redirect(url_for('service_catalog'))

@app.route('/containers/<int:container_id>/status')
@login_required
def container_status(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    status = podman_manager.get_container_status(container.container_id)
    return jsonify({'status': status})

@app.route('/admin/podman-status')
@login_required
@admin_required
def podman_status():
    status, message = podman_manager.check_system()
    return jsonify({
        'status': 'ok' if status else 'error',
        'message': message
    })