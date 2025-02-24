from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models import Service, Container
import logging

main = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main.route('/')
def index():
    """Display landing page with featured services"""
    try:
        services = Service.query.filter_by(is_active=True).order_by(Service.price).all()
        logger.info(f"Successfully loaded {len(services)} services for index page")
        return render_template('index.html', 
                            services=services,
                            current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading index page: {str(e)}")
        flash('Error loading services. Please try again later.', 'danger')
        return render_template('index.html', 
                            services=[],
                            current_user=current_user)

@main.route('/dashboard')
@login_required
def dashboard():
    """Display user dashboard without sidebar"""
    try:
        services = Service.query.filter_by(is_active=True).all()
        total_cpu_usage = sum(container.cpu_usage for container in current_user.containers)
        total_memory_usage = sum(container.memory_usage for container in current_user.containers)
        total_storage_usage = sum(container.storage_usage for container in current_user.containers)

        return render_template('dashboard.html',
                            services=services,
                            total_cpu_usage=total_cpu_usage,
                            total_memory_usage=total_memory_usage,
                            total_storage_usage=total_storage_usage)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash('Error loading dashboard. Please try again later.', 'danger')
        return render_template('dashboard.html', services=[])

@main.route('/services/catalog')
def service_catalog():
    """Display full service catalog"""
    try:
        logger.debug("Fetching services for catalog")
        services = Service.query.filter_by(is_active=True).all()
        logger.info(f"Successfully found {len(services)} services")
        return render_template('services/catalog.html', 
                            services=services,
                            current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading service catalog: {str(e)}")
        return render_template('services/catalog.html', 
                            services=[],
                            current_user=current_user)
        

@main.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    try:
        service = Service.query.get_or_404(service_id)
        logger.info(f"Attempting to deploy service {service.name} for user {current_user.id}")

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
            logger.info(f"Successfully deployed service {service.name} for user {current_user.id}")
            flash('Service deployed successfully!', 'success')
        else:
            logger.error(f"Failed to deploy service {service.name} for user {current_user.id}")
            flash('Failed to deploy service', 'danger')

        return redirect(url_for('main.service_catalog'))

    except Exception as e:
        logger.error(f"Error deploying service: {str(e)}")
        flash('Error deploying service. Please try again later.', 'danger')
        return redirect(url_for('main.service_catalog'))