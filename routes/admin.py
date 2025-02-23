from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models import User, Service
from utils import admin_required
from utils.podman import podman_manager
import logging

admin = Blueprint('admin', __name__)

@admin.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    services = Service.query.all()
    return render_template('admin/dashboard.html', users=users, services=services)

@admin.route('/admin/podman-status')
@login_required
@admin_required
def podman_status():
    status, message = podman_manager.check_system()
    return jsonify({
        'status': 'ok' if status else 'error',
        'message': message
    })