from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_customer_id = db.Column(db.String(120), unique=True)
    # 2FA fields
    two_factor_secret = db.Column(db.String(32))
    two_factor_enabled = db.Column(db.Boolean, default=False)
    profile = db.relationship('CustomerProfile', backref='user', uselist=False)
    containers = db.relationship('Container', backref='user', lazy='dynamic')
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_2fa_uri(self):
        """Generate the 2FA provisioning URI"""
        if self.two_factor_secret:
            return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
                name=self.email,
                issuer_name="Cloud Service Management"
            )
        return None

    def verify_2fa(self, code):
        """Verify a 2FA code"""
        if not self.two_factor_enabled or not self.two_factor_secret:
            return True
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(code)

    def enable_2fa(self):
        """Enable 2FA for the user"""
        if not self.two_factor_secret:
            self.two_factor_secret = pyotp.random_base32()
        self.two_factor_enabled = True
        return self.get_2fa_uri()

    def disable_2fa(self):
        """Disable 2FA for the user"""
        self.two_factor_enabled = False
        self.two_factor_secret = None

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_price_id = db.Column(db.String(120))
    stripe_product_id = db.Column(db.String(120))
    container_image = db.Column(db.String(200))
    container_port = db.Column(db.Integer)
    environment_vars = db.Column(db.JSON)
    subscriptions = db.relationship('Subscription', backref='service', lazy='dynamic')

class Container(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    service = db.relationship('Service', backref=db.backref('containers', lazy='dynamic'))
    port = db.Column(db.Integer)
    environment = db.Column(db.JSON)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(120), unique=True)
    status = db.Column(db.String(20), default='inactive')
    current_period_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)