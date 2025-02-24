from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user, login_required
from utils.podman import podman_manager

def admin_required(f):
    @wraps(f)
    @login_required  # First ensure user is logged in
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

__all__ = ['admin_required', 'podman_manager']