from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager, limiter
from models import User, Service, CustomerProfile, BillingInfo
from utils import admin_required
from werkzeug.security import generate_password_hash

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
