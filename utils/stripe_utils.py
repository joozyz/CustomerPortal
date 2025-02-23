import os
import stripe
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from models import User, Service, Subscription, BillingInfo

logger = logging.getLogger(__name__)

def init_stripe() -> Tuple[bool, str]:
    """Initialize Stripe configuration and validate API keys"""
    try:
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe.api_key:
            return False, "Stripe secret key not found in environment"

        # Verify API key by making a test API call
        stripe.Account.retrieve()
        logger.info("Stripe API initialized successfully")
        return True, "Stripe initialized successfully"
    except stripe.error.AuthenticationError:
        logger.error("Invalid Stripe API key")
        return False, "Invalid Stripe API key"
    except Exception as e:
        logger.error(f"Error initializing Stripe: {str(e)}")
        return False, f"Error initializing Stripe: {str(e)}"

def create_stripe_customer(user: User) -> Optional[str]:
    """Create a Stripe customer for a user"""
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username,
            metadata={'user_id': str(user.id)}
        )
        logger.info(f"Created Stripe customer for user {user.id}")
        return customer.id
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating customer: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error creating Stripe customer: {str(e)}")
        return None

def create_stripe_product(service: Service) -> Optional[Dict[str, str]]:
    """Create a Stripe product and price for a service"""
    try:
        product = stripe.Product.create(
            name=service.name,
            description=service.description,
            metadata={'service_id': str(service.id)}
        )

        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(service.price * 100),  # Convert to cents
            currency='usd',
            recurring={'interval': 'month'}
        )

        logger.info(f"Created Stripe product and price for service {service.id}")
        return {
            'product_id': product.id,
            'price_id': price.id
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating product: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error creating Stripe product: {str(e)}")
        return None

def create_subscription(user: User, service: Service, payment_method_id: str) -> Optional[Dict[str, Any]]:
    """Create a Stripe subscription for a user"""
    try:
        # Attach payment method to customer
        stripe.PaymentMethod.attach(payment_method_id, customer=user.stripe_customer_id)

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

        logger.info(f"Created subscription for user {user.id} and service {service.id}")
        return {
            'subscription_id': subscription.id,
            'client_secret': subscription.latest_invoice.payment_intent.client_secret,
            'status': subscription.status
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return None

def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a Stripe subscription"""
    try:
        stripe.Subscription.delete(subscription_id)
        logger.info(f"Cancelled subscription {subscription_id}")
        return True
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return False

def update_payment_method(user: User, payment_method_id: str) -> Optional[Dict[str, Any]]:
    """Update payment method for a user"""
    try:
        # Attach the payment method to the customer
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

        # Get payment method details
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

        logger.info(f"Updated payment method for user {user.id}")
        return {
            'card_last4': payment_method.card.last4,
            'card_brand': payment_method.card.brand
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error updating payment method: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error updating payment method: {str(e)}")
        return None

# Initialize Stripe when module is imported
stripe_status, stripe_message = init_stripe()
if not stripe_status:
    logger.warning(f"Failed to initialize Stripe: {stripe_message}")