from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models import Service, Container
from utils.podman_manager import podman_manager
import logging

main = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main.route('/')
def index():
    try:
        services = Service.query.all()
        logger.debug(f"Found {len(services)} services")
        return render_template('index.html', services=services)
    except Exception as e:
        logger.error(f"Error loading services: {str(e)}")
        flash('Error loading services', 'danger')
        return render_template('index.html', services=[])

@main.route('/services/catalog')
def service_catalog():
    try:
        services = Service.query.all()
        return render_template('services/catalog.html', services=services)
    except Exception as e:
        logger.error(f"Error loading service catalog: {str(e)}")
        flash('Error loading service catalog', 'danger')
        return render_template('services/catalog.html', services=[])

@main.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    try:
        service = Service.query.get_or_404(service_id)

        # Check if service is already deployed
        existing = Container.query.filter_by(
            user_id=current_user.id,
            service_id=service_id,
            status='running'
        ).first()

        if existing:
            flash('Service is already deployed', 'warning')
            return redirect(url_for('main.service_catalog'))

        # Deploy using Podman
        container = podman_manager.deploy_service(
            service=service,
            user_id=current_user.id,
            environment=service.environment_vars
        )

        if container:
            db.session.add(container)
            db.session.commit()
            flash('Service deployed successfully!', 'success')
        else:
            flash('Failed to deploy service', 'danger')

        return redirect(url_for('main.service_catalog'))

    except Exception as e:
        logger.error(f"Error deploying service: {str(e)}")
        flash('Error deploying service', 'danger')
        return redirect(url_for('main.service_catalog'))