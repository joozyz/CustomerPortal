from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from models import User, CustomerProfile
import logging

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
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

@auth.route('/register', methods=['GET', 'POST'])
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
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))