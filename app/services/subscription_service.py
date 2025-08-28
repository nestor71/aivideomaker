"""
Subscription Service for AIVideoMaker Freemium system
Handles Stripe subscriptions, tier management, and billing
"""

import stripe
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database.models import User, Subscription, PaymentHistory, SubscriptionTier, SubscriptionStatus, PaymentStatus
from app.core.config import settings
from app.core.logger import logger

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def create_stripe_customer(self, user: User, email: str) -> str:
        """Create Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=user.name,
                metadata={'user_id': str(user.id)}
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise HTTPException(status_code=400, detail="Failed to create customer")

    def create_subscription(self, user: User, price_id: str, payment_method_id: str) -> Subscription:
        """Create new subscription"""
        try:
            # Create Stripe customer if not exists
            if not user.stripe_customer_id:
                user.stripe_customer_id = self.create_stripe_customer(user, user.email)
                self.db.commit()

            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=user.stripe_customer_id,
            )

            # Set as default payment method
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id,
                },
            )

            # Create subscription
            stripe_subscription = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent'],
            )

            # Save to database
            subscription = Subscription(
                user_id=user.id,
                stripe_subscription_id=stripe_subscription.id,
                tier=SubscriptionTier.PREMIUM,
                status=SubscriptionStatus.ACTIVE,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                auto_renew=True
            )
            
            self.db.add(subscription)
            self.db.commit()
            
            return subscription

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise HTTPException(status_code=400, detail="Failed to create subscription")

    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel subscription"""
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()
            
            if not subscription:
                raise HTTPException(status_code=404, detail="Subscription not found")

            # Cancel in Stripe
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )

            # Update database
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.utcnow()
            self.db.commit()

            return True

        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise HTTPException(status_code=400, detail="Failed to cancel subscription")

    def handle_webhook(self, event: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events"""
        try:
            if event['type'] == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                return self._handle_payment_failed(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event['data']['object'])
            
            return True

        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return False

    def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> bool:
        """Handle successful payment"""
        try:
            subscription_id = invoice['subscription']
            subscription = self.db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()

            if subscription:
                # Create payment history record
                payment_history = PaymentHistory(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    stripe_payment_intent_id=invoice['payment_intent'],
                    amount=invoice['amount_paid'] / 100,  # Convert from cents
                    currency=invoice['currency'],
                    status=PaymentStatus.SUCCEEDED
                )
                
                self.db.add(payment_history)
                
                # Update subscription
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.end_date = datetime.utcnow() + timedelta(days=30)
                
                self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to handle payment success: {e}")
            return False

    def _handle_payment_failed(self, invoice: Dict[str, Any]) -> bool:
        """Handle failed payment"""
        try:
            subscription_id = invoice['subscription']
            subscription = self.db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()

            if subscription:
                # Create payment history record
                payment_history = PaymentHistory(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    stripe_payment_intent_id=invoice['payment_intent'],
                    amount=invoice['amount_due'] / 100,  # Convert from cents
                    currency=invoice['currency'],
                    status=PaymentStatus.FAILED
                )
                
                self.db.add(payment_history)
                
                # Update subscription status
                subscription.status = SubscriptionStatus.PAST_DUE
                
                self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to handle payment failure: {e}")
            return False

    def _handle_subscription_deleted(self, subscription_data: Dict[str, Any]) -> bool:
        """Handle subscription deletion"""
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_data['id']
            ).first()

            if subscription:
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.cancelled_at = datetime.utcnow()
                self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to handle subscription deletion: {e}")
            return False

    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get user's active subscription"""
        return self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE])
        ).first()

    def check_subscription_limits(self, user: User) -> Dict[str, Any]:
        """Check user's subscription limits"""
        subscription = self.get_user_subscription(user.id)
        
        if not subscription or subscription.tier == SubscriptionTier.FREE:
            return {
                "tier": "free",
                "video_limit": 10,  # minutes per month
                "max_duration": 1,  # minute per video
                "max_resolution": "720p",
                "watermark": True,
                "api_calls_limit": 50
            }
        
        return {
            "tier": "premium",
            "video_limit": -1,  # unlimited
            "max_duration": -1,  # unlimited
            "max_resolution": "4K",
            "watermark": False,
            "api_calls_limit": -1  # unlimited
        }

    def upgrade_to_premium(self, user: User, payment_method_id: str) -> Subscription:
        """Upgrade user to premium"""
        price_id = settings.STRIPE_PREMIUM_PRICE_ID
        return self.create_subscription(user, price_id, payment_method_id)

    def get_billing_history(self, user: User) -> List[PaymentHistory]:
        """Get user's billing history"""
        return self.db.query(PaymentHistory).filter(
            PaymentHistory.user_id == user.id
        ).order_by(PaymentHistory.created_at.desc()).all()

    def create_billing_portal_session(self, user: User) -> str:
        """Create Stripe billing portal session"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"{settings.FRONTEND_URL}/dashboard"
            )
            return session.url

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create billing portal session: {e}")
            raise HTTPException(status_code=400, detail="Failed to create billing session")

    def create_checkout_session(self, user: User) -> str:
        """Create Stripe checkout session for premium upgrade"""
        try:
            # Create customer if not exists
            if not user.stripe_customer_id:
                user.stripe_customer_id = self.create_stripe_customer(user, user.email)
                self.db.commit()

            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': settings.STRIPE_PREMIUM_PRICE_ID,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{settings.FRONTEND_URL}/dashboard?upgrade=success",
                cancel_url=f"{settings.FRONTEND_URL}/dashboard?upgrade=cancelled",
                metadata={'user_id': str(user.id)}
            )
            
            return session.url

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise HTTPException(status_code=400, detail="Failed to create checkout session")

    def is_premium_user(self, user: User) -> bool:
        """Check if user has active premium subscription"""
        subscription = self.get_user_subscription(user.id)
        return (subscription and 
                subscription.tier == SubscriptionTier.PREMIUM and 
                subscription.status == SubscriptionStatus.ACTIVE)

    def get_subscription_analytics(self) -> Dict[str, Any]:
        """Get subscription analytics for admin dashboard"""
        from sqlalchemy import func, extract
        
        # Total subscriptions by status
        status_counts = self.db.query(
            Subscription.status,
            func.count(Subscription.id).label('count')
        ).group_by(Subscription.status).all()

        # Monthly revenue
        monthly_revenue = self.db.query(
            extract('month', PaymentHistory.created_at).label('month'),
            func.sum(PaymentHistory.amount).label('revenue')
        ).filter(
            PaymentHistory.status == PaymentStatus.SUCCEEDED,
            extract('year', PaymentHistory.created_at) == datetime.now().year
        ).group_by(extract('month', PaymentHistory.created_at)).all()

        # Conversion rate
        total_users = self.db.query(User).count()
        premium_users = self.db.query(Subscription).filter(
            Subscription.tier == SubscriptionTier.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0

        return {
            "status_distribution": {str(status): count for status, count in status_counts},
            "monthly_revenue": {int(month): float(revenue) for month, revenue in monthly_revenue},
            "total_users": total_users,
            "premium_users": premium_users,
            "conversion_rate": round(conversion_rate, 2),
            "mrr": float(premium_users * 9.99),  # Monthly recurring revenue
        }