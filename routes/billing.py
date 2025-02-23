from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Service, Subscription, BillingInfo
from utils.stripe_utils import (
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

@billing.route('/setup', methods=['GET', 'POST'])
@login_required
def setup_billing():
    """Handle billing setup and create Stripe checkout session"""
    if request.method == 'POST':
        try:
            logger.info(f"Starting billing setup for user {current_user.id}")

            if not current_user.stripe_customer_id:
                logger.info("Creating new Stripe customer")
                customer_id = create_stripe_customer(current_user)
                if not customer_id:
                    logger.error("Failed to create Stripe customer")
                    raise Exception("Failed to create Stripe customer")

                current_user.stripe_customer_id = customer_id
                db.session.commit()
                logger.info(f"Created Stripe customer: {customer_id}")

            # Create Stripe Checkout session for setup
            session = stripe.checkout.Session.create(
                customer=current_user.stripe_customer_id,
                payment_method_types=['card'],
                mode='setup',
                success_url=request.host_url.rstrip('/') + url_for('billing.setup_success'),
                cancel_url=request.host_url.rstrip('/') + url_for('billing.setup_cancelled'),
            )

            logger.info(f"Created Stripe session: {session.id}")
            return redirect(session.url)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error during setup: {str(e)}")
            flash('An error occurred with the payment processor. Please try again.', 'danger')
            return redirect(url_for('billing.setup_billing'))
        except Exception as e:
            logger.error(f"Error during billing setup: {str(e)}")
            flash('Failed to initialize payment setup. Please try again.', 'danger')
            return redirect(url_for('billing.setup_billing'))

    return render_template('billing/setup.html',
                         stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'))

@billing.route('/setup/success')
@login_required
def setup_success():
    """Handle successful payment method setup"""
    try:
        # Verify the setup was successful
        if not current_user.stripe_customer_id:
            logger.error("Setup success called but no Stripe customer ID found")
            flash('There was an error setting up your payment method.', 'danger')
            return redirect(url_for('billing.setup_billing'))

        # Create or update billing info
        billing_info = BillingInfo.query.filter_by(profile_id=current_user.profile.id).first()
        if not billing_info:
            billing_info = BillingInfo(profile=current_user.profile)
            db.session.add(billing_info)

        db.session.commit()
        logger.info(f"Payment setup completed successfully for user {current_user.id}")
        flash('Payment method added successfully!', 'success')

    except Exception as e:
        logger.error(f"Error in setup success: {str(e)}")
        flash('There was an error completing your payment setup.', 'danger')

    return redirect(url_for('service.dashboard'))

@billing.route('/setup/cancelled')
@login_required
def setup_cancelled():
    """Handle cancelled payment method setup"""
    logger.info(f"Payment setup cancelled by user {current_user.id}")
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