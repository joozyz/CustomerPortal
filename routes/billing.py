from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Service, Subscription, BillingInfo
from utils.stripe_utils import (
    init_stripe,
    create_stripe_customer,
    create_subscription,
    cancel_subscription,
    update_payment_method
)
from datetime import datetime
import logging
import stripe
import os

billing = Blueprint('billing', __name__)
logger = logging.getLogger(__name__)

@billing.before_request
def check_stripe_status():
    """Verify Stripe is properly initialized before handling any billing routes"""
    stripe_status, message = init_stripe()
    if not stripe_status and request.endpoint != 'billing.setup_billing':
        flash('Payment system is currently unavailable. Please try again later.', 'danger')
        return redirect(url_for('service.dashboard'))

@billing.route('/billing/setup', methods=['GET'])
@login_required
def setup_billing():
    return render_template('billing/setup.html', 
                         stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'))

@billing.route('/billing/create-setup-session', methods=['POST'])
@login_required
def create_setup_session():
    try:
        if not current_user.stripe_customer_id:
            # Create a new Stripe customer
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        # Create Stripe Checkout session for setup
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            mode='setup',
            success_url=request.host_url.rstrip('/') + url_for('billing.setup_success'),
            cancel_url=request.host_url.rstrip('/') + url_for('billing.setup_cancelled'),
        )

        return jsonify({'id': session.id})
    except Exception as e:
        logger.error(f"Error creating setup session: {str(e)}")
        return jsonify({'error': 'Failed to create setup session'}), 500

@billing.route('/billing/setup/success')
@login_required
def setup_success():
    flash('Payment method added successfully!', 'success')
    return redirect(url_for('service.dashboard'))

@billing.route('/billing/setup/cancelled')
@login_required
def setup_cancelled():
    flash('Payment setup was cancelled.', 'warning')
    return redirect(url_for('service.dashboard'))

@billing.route('/billing/subscribe/<int:service_id>', methods=['POST'])
@login_required
def subscribe_service(service_id):
    service = Service.query.get_or_404(service_id)

    if not current_user.stripe_customer_id:
        flash('Please set up billing first', 'warning')
        return redirect(url_for('billing.setup_billing'))

    try:
        # Create Stripe Checkout session for subscription
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': service.stripe_price_id,
                'quantity': 1,
            }],
            success_url=request.host_url.rstrip('/') + url_for('billing.subscription_success', service_id=service_id),
            cancel_url=request.host_url.rstrip('/') + url_for('service.service_catalog'),
        )

        return redirect(session.url)
    except Exception as e:
        logger.error(f"Error creating subscription session: {str(e)}")
        flash('An error occurred while processing your subscription', 'danger')
        return redirect(url_for('service.service_catalog'))

@billing.route('/billing/subscription/success/<int:service_id>')
@login_required
def subscription_success(service_id):
    service = Service.query.get_or_404(service_id)
    subscription = Subscription(
        user=current_user,
        service=service,
        status='active',
        current_period_end=datetime.utcnow()  # Will be updated by webhook
    )
    db.session.add(subscription)
    db.session.commit()
    flash('Successfully subscribed to service!', 'success')
    return redirect(url_for('service.dashboard'))

@billing.route('/billing/cancel/<int:subscription_id>', methods=['POST'])
@login_required
def cancel_service_subscription(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)

    if subscription.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('service.dashboard'))

    try:
        if cancel_subscription(subscription.stripe_subscription_id):
            subscription.status = 'cancelled'
            subscription.cancelled_at = datetime.utcnow()
            db.session.commit()
            flash('Subscription cancelled successfully', 'success')
        else:
            flash('Failed to cancel subscription', 'danger')
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        flash('An error occurred while cancelling your subscription', 'danger')

    return redirect(url_for('service.dashboard'))