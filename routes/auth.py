from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, limiter
from models import User, CustomerProfile
import qrcode
import io
import base64
import logging

from forms import LoginForm

auth = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            logging.info(f"User {form.email.data} logged in successfully")
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.index'))
        flash('Invalid email or password', 'danger')
        logging.warning(f"Failed login attempt for email: {form.email.data}")

    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('service.dashboard'))

    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))

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
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    if request.method == 'POST':
        code = request.form.get('code')
        if not code:
            flash('Please provide the verification code', 'danger')
            return redirect(url_for('auth.setup_2fa'))

        if current_user.verify_2fa(code):
            current_user.two_factor_enabled = True
            db.session.commit()
            flash('Two-factor authentication enabled successfully', 'success')
            return redirect(url_for('service.dashboard'))
        else:
            flash('Invalid verification code', 'danger')

    if not current_user.two_factor_secret:
        qr_uri = current_user.enable_2fa()
        db.session.commit()
    else:
        qr_uri = current_user.get_2fa_uri()

    # Generate QR code
    img = qrcode.make(qr_uri)
    img_buffer = io.BytesIO()
    img.save(img_buffer)
    img_str = base64.b64encode(img_buffer.getvalue()).decode()

    return render_template('auth/setup_2fa.html', qr_code=img_str)

@auth.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    current_user.disable_2fa()
    db.session.commit()
    flash('Two-factor authentication disabled', 'success')
    return redirect(url_for('service.dashboard'))

@auth.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    if not session.get('email_2fa'):
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code')
        user = User.query.filter_by(email=session['email_2fa']).first()

        if user and user.verify_2fa(code):
            login_user(user)
            session.pop('email_2fa', None)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('service.dashboard'))
        else:
            flash('Invalid verification code', 'danger')

    return render_template('auth/verify_2fa.html')

from app import app
from flask import abort