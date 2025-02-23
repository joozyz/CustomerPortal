from flask import Blueprint, render_template
from models import Service

main = Blueprint('main', __name__)

@main.route('/')
def index():
    services = Service.query.all()
    return render_template('index.html', services=services)