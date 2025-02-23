import os
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from models import User, Service, Subscription, BillingInfo

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)

def create_stripe_customer(user: User) -> Optional[str]:
    """Create a Stripe customer for a user"""
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username,
            metadata={'user_id': user.id}
        )
        return customer.id
    except Exception as e:
        logger.error(f"Error creating Stripe customer: {str(e)}")
        return None

def create_stripe_product(service: Service) -> Optional[Dict[str, str]]:
    """Create a Stripe product and price for a service"""
    try:
        product = stripe.Product.create(
            name=service.name,
            description=service.description,
            metadata={'service_id': service.id}
        )

        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(service.price * 100),  # Convert to cents
            currency='usd',
            recurring={'interval': 'month'}
        )

        return {
            'product_id': product.id,
            'price_id': price.id
        }
    except Exception as e:
        logger.error(f"Error creating Stripe product: {str(e)}")
        return None

def create_subscription(user: User, service: Service, payment_method_id: str) -> Optional[Dict[str, Any]]:
    """Create a Stripe subscription for a user"""
    try:
        # Attach payment method to customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=user.stripe_customer_id
        )

        # Set as default payment method
        stripe.Customer.modify(
            user.stripe_customer_id,
            invoice_settings={
                'default_payment_method': payment_method_id
            }
        )

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=user.stripe_customer_id,
            items=[{'price': service.stripe_price_id}],
            expand=['latest_invoice.payment_intent']
        )

        return {
            'subscription_id': subscription.id,
            'client_secret': subscription.latest_invoice.payment_intent.client_secret,
            'status': subscription.status
        }
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return None

def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a Stripe subscription"""
    try:
        stripe.Subscription.delete(subscription_id)
        return True
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return False

def update_payment_method(user: User, payment_method_id: str) -> Optional[Dict[str, Any]]:
    """Update payment method for a user"""
    try:
        payment_method = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=user.stripe_customer_id
        )

        stripe.Customer.modify(
            user.stripe_customer_id,
            invoice_settings={
                'default_payment_method': payment_method_id
            }
        )

        return {
            'card_last4': payment_method.card.last4,
            'card_brand': payment_method.card.brand
        }
    except Exception as e:
        logger.error(f"Error updating payment method: {str(e)}")
        return None
