from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import app, db, limiter
from models import Service, Container
from utils import admin_required, podman_manager
import logging

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