from datetime import datetime, timedelta
import secrets
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
import logging
from database import db

logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_customer_id = db.Column(db.String(120), unique=True)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    two_factor_secret = db.Column(db.String(32))
    two_factor_enabled = db.Column(db.Boolean, default=False)
    profile = db.relationship('CustomerProfile', backref='user', uselist=False)
    containers = db.relationship('Container', backref='user', lazy='dynamic')
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        return self.reset_token

    def verify_reset_token(self, token):
        if (self.reset_token != token or 
            not self.reset_token_expiry or 
            self.reset_token_expiry < datetime.utcnow()):
            return False
        return True

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None
        db.session.commit()

    def get_2fa_uri(self):
        if self.two_factor_secret:
            return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
                name=self.email,
                issuer_name="Cloud Service Management"
            )
        return None

    def verify_2fa(self, code):
        if not self.two_factor_enabled or not self.two_factor_secret:
            return True
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(code)

    def enable_2fa(self):
        if not self.two_factor_secret:
            self.two_factor_secret = pyotp.random_base32()
        self.two_factor_enabled = True
        return self.get_2fa_uri()

    def disable_2fa(self):
        self.two_factor_enabled = False
        self.two_factor_secret = None

    def delete(self):
        if self.stripe_customer_id:
            try:
                import stripe
                stripe.Customer.delete(self.stripe_customer_id)
            except Exception as e:
                logger.error(f"Error deleting Stripe customer: {str(e)}")
        super().delete()

class CustomerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    billing_info = db.relationship('BillingInfo', backref='profile', uselist=False)

class BillingInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('customer_profile.id'), nullable=False)
    stripe_payment_method_id = db.Column(db.String(120))
    card_last4 = db.Column(db.String(4))
    card_brand = db.Column(db.String(20))
    billing_address = db.Column(db.String(200))

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_price_id = db.Column(db.String(120))
    stripe_product_id = db.Column(db.String(120))
    container_image = db.Column(db.String(200))
    container_port = db.Column(db.Integer)
    environment_vars = db.Column(db.JSON)
    cpu_quota = db.Column(db.Float, default=1.0)  
    memory_quota = db.Column(db.Integer, default=512)  
    storage_quota = db.Column(db.Integer, default=1024)  
    domain = db.Column(db.String(255))  
    domain_status = db.Column(db.String(20), default='pending')  
    ssl_enabled = db.Column(db.Boolean, default=False)
    ssl_expiry = db.Column(db.DateTime)
    backup_enabled = db.Column(db.Boolean, default=True)
    backup_frequency = db.Column(db.String(20), default='daily')  
    backup_retention_days = db.Column(db.Integer, default=7)
    last_backup_at = db.Column(db.DateTime)
    backup_storage_path = db.Column(db.String(255))
    monitoring_enabled = db.Column(db.Boolean, default=True)
    alert_email = db.Column(db.String(120))
    alert_phone = db.Column(db.String(20))
    subscriptions = db.relationship('Subscription', backref='service', lazy='dynamic')
    containers = db.relationship('Container', backref='service', lazy='dynamic')

    def initialize_backup_config(self):
        if not self.backup_storage_path:
            self.backup_storage_path = f"/backups/{self.name.lower()}"
        if not self.backup_frequency:
            self.backup_frequency = 'daily'
        if not self.backup_retention_days:
            self.backup_retention_days = 7

class Container(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    port = db.Column(db.Integer)
    environment = db.Column(db.JSON)
    cpu_usage = db.Column(db.Float, default=0.0)
    memory_usage = db.Column(db.Integer, default=0)
    storage_usage = db.Column(db.Integer, default=0)
    last_backup = db.Column(db.DateTime)
    last_monitored = db.Column(db.DateTime)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(120), unique=True)
    status = db.Column(db.String(20), default='inactive')
    current_period_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)

class SystemActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('activities', lazy='dynamic'))

    @classmethod
    def log_activity(cls, action, description, user=None):
        activity = cls(
            action=action,
            description=description,
            user_id=user.id if user else None
        )
        db.session.add(activity)
        db.session.commit()

class SystemAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(20), default='info')  
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    resolved_by = db.relationship('User', backref=db.backref('resolved_alerts', lazy='dynamic'))

    @classmethod
    def create_alert(cls, title, message, level='info'):
        alert = cls(
            title=title,
            message=message,
            level=level
        )
        db.session.add(alert)
        db.session.commit()
        return alert

    def resolve(self, user):
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user
        db.session.commit()

class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    is_secret = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_setting(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_setting(cls, key, value, description=None, is_secret=False):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key, description=description, is_secret=is_secret)
        setting.value = value
        db.session.add(setting)
        db.session.commit()
        return setting