from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Service, Subscription, BillingInfo
from utils.stripe_utils import (
    create_stripe_customer,
    create_subscription,
    cancel_subscription,
    update_payment_method
)
import logging

billing = Blueprint('billing', __name__)

@billing.route('/billing/setup', methods=['GET', 'POST'])
@login_required
def setup_billing():
    if request.method == 'POST':
        try:
            payment_method_id = request.form.get('payment_method_id')
            if not current_user.stripe_customer_id:
                customer_id = create_stripe_customer(current_user)
                if customer_id:
                    current_user.stripe_customer_id = customer_id
                    db.session.commit()
                else:
                    flash('Failed to setup billing. Please try again.', 'danger')
                    return redirect(url_for('billing.setup_billing'))

            # Update payment method
            result = update_payment_method(current_user, payment_method_id)
            if result:
                if not current_user.profile.billing_info:
                    billing_info = BillingInfo(
                        profile=current_user.profile,
                        card_last4=result['card_last4'],
                        card_brand=result['card_brand']
                    )
                    db.session.add(billing_info)
                else:
                    current_user.profile.billing_info.card_last4 = result['card_last4']
                    current_user.profile.billing_info.card_brand = result['card_brand']
                db.session.commit()
                flash('Payment method updated successfully', 'success')
            else:
                flash('Failed to update payment method', 'danger')

        except Exception as e:
            logging.error(f"Error setting up billing: {str(e)}")
            flash('An error occurred while setting up billing', 'danger')

        return redirect(url_for('dashboard'))

    return render_template('billing/setup.html')

@billing.route('/billing/subscribe/<int:service_id>', methods=['POST'])
@login_required
def subscribe_service(service_id):
    service = Service.query.get_or_404(service_id)
    payment_method_id = request.form.get('payment_method_id')

    if not current_user.stripe_customer_id:
        flash('Please set up billing first', 'warning')
        return redirect(url_for('billing.setup_billing'))

    try:
        subscription_data = create_subscription(current_user, service, payment_method_id)
        if subscription_data:
            subscription = Subscription(
                user=current_user,
                service=service,
                stripe_subscription_id=subscription_data['subscription_id'],
                status=subscription_data['status']
            )
            db.session.add(subscription)
            db.session.commit()
            flash('Successfully subscribed to service', 'success')
        else:
            flash('Failed to create subscription', 'danger')
    except Exception as e:
        logging.error(f"Error creating subscription: {str(e)}")
        flash('An error occurred while processing your subscription', 'danger')

    return redirect(url_for('dashboard'))

@billing.route('/billing/cancel/<int:subscription_id>', methods=['POST'])
@login_required
def cancel_service_subscription(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    
    if subscription.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('dashboard'))

    try:
        if cancel_subscription(subscription.stripe_subscription_id):
            subscription.status = 'cancelled'
            subscription.cancelled_at = datetime.utcnow()
            db.session.commit()
            flash('Subscription cancelled successfully', 'success')
        else:
            flash('Failed to cancel subscription', 'danger')
    except Exception as e:
        logging.error(f"Error cancelling subscription: {str(e)}")
        flash('An error occurred while cancelling your subscription', 'danger')

    return redirect(url_for('dashboard'))
