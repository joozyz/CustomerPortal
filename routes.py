from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager, limiter
from models import User, Service, CustomerProfile, BillingInfo, Container
from utils import admin_required, podman_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    services = Service.query.all()
    return render_template('index.html', services=services)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'danger')
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

@app.route('/services/<int:service_id>/deploy', methods=['POST'])
@login_required
def deploy_service(service_id):
    service = Service.query.get_or_404(service_id)

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
        db.session.add(container)
        db.session.commit()
        flash('Service deployed successfully', 'success')
    else:
        flash('Failed to deploy service', 'danger')

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