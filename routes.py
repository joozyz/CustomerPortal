from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager, limiter
from models import User, Service, CustomerProfile, BillingInfo, Container
from utils import admin_required, podman_manager
import logging

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Please provide both email and password', 'danger')
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                logging.info(f"User {email} logged in successfully")
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                logging.warning(f"Failed login attempt for email: {email}")
                flash('Invalid email or password', 'danger')
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            flash('An error occurred during login', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        user = User(
            username=request.form.get('username'),
            email=request.form.get('email')
        )
        user.set_password(request.form.get('password'))

        profile = CustomerProfile(
            company_name=request.form.get('company_name'),
            phone=request.form.get('phone'),
            address=request.form.get('address')
        )
        user.profile = profile

        db.session.add(user)
        db.session.commit()

        flash('Registration successful!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    return render_template('dashboard.html')

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    services = Service.query.all()
    return render_template('admin/dashboard.html', users=users, services=services)

@app.route('/services/catalog')
def service_catalog():
    services = Service.query.all()
    return render_template('services/catalog.html', services=services)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/services/<int:service_id>/update', methods=['POST'])
@login_required
@admin_required
def update_service(service_id):
    service = Service.query.get_or_404(service_id)

    if request.method == 'POST':
        service.name = request.form.get('name')
        service.description = request.form.get('description')
        service.price = float(request.form.get('price'))

        if service.container_image:
            service.container_image = request.form.get('container_image')
            service.container_port = int(request.form.get('container_port'))

        db.session.commit()
        flash('Service updated successfully', 'success')

    return redirect(url_for('service_catalog'))

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

@app.route('/containers/<int:container_id>/stop', methods=['POST'])
@login_required
def stop_container(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('dashboard'))

    if podman_manager.stop_container(container.container_id):
        container.status = 'stopped'
        db.session.commit()
        flash('Container stopped successfully', 'success')
    else:
        flash('Failed to stop container', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/containers/<int:container_id>/remove', methods=['POST'])
@login_required
def remove_container(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('dashboard'))

    if podman_manager.remove_container(container.container_id):
        db.session.delete(container)
        db.session.commit()
        flash('Container removed successfully', 'success')
    else:
        flash('Failed to remove container', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/containers/<int:container_id>/status')
@login_required
def container_status(container_id):
    container = Container.query.get_or_404(container_id)

    # Ensure the container belongs to the current user
    if container.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    status = podman_manager.get_container_status(container.container_id)
    return jsonify({'status': status})

@app.route('/')
def index():
    services = Service.query.all()
    return render_template('index.html', services=services)

@app.route('/admin/podman-status')
@login_required
@admin_required
def podman_status():
    status, message = podman_manager.check_system()
    return jsonify({
        'status': 'ok' if status else 'error',
        'message': message
    })