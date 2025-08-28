import stripe
from typing import Dict, Optional, Any
from sqlalchemy.orm import Session
from app.database.models import User, Subscription, PaymentHistory, SubscriptionTier, SubscriptionStatus, PaymentStatus
from app.core.config import settings
from app.core.logger import logger
from app.services.email_service import email_service
from datetime import datetime, timedelta

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Stripe payment integration service."""
    
    def __init__(self):
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    async def create_customer(self, user: User) -> str:
        """Create Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={
                    "user_id": str(user.id),
                    "app": "aivideomaker"
                }
            )
            
            logger.info(f"Stripe customer created: {customer.id} for user {user.id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation error: {e}")
            raise Exception(f"Failed to create customer: {str(e)}")
    
    async def create_subscription(
        self,
        db: Session,
        user: User,
        payment_method_id: str,
        tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """Create subscription with payment method."""
        try:
            # Get or create Stripe customer
            if not user.subscription or not user.subscription.stripe_customer_id:
                customer_id = await self.create_customer(user)
                
                # Update subscription with customer ID
                if user.subscription:
                    user.subscription.stripe_customer_id = customer_id
                    db.commit()
            else:
                customer_id = user.subscription.stripe_customer_id
            
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            
            # Determine price based on tier
            price_id = self._get_price_id(tier)
            if not price_id:
                raise Exception(f"Price not configured for tier: {tier}")
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent'],
                metadata={
                    "user_id": str(user.id),
                    "tier": tier.value
                }
            )
            
            # Update database
            await self._update_subscription_from_stripe(db, user, subscription)
            
            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret,
                "status": subscription.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation error: {e}")
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    async def update_subscription(
        self,
        db: Session,
        user: User,
        new_tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """Update existing subscription tier."""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise Exception("No active subscription found")
            
            stripe_subscription = stripe.Subscription.retrieve(
                user.subscription.stripe_subscription_id
            )
            
            # Get new price
            new_price_id = self._get_price_id(new_tier)
            if not new_price_id:
                raise Exception(f"Price not configured for tier: {new_tier}")
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                stripe_subscription.id,
                items=[{
                    'id': stripe_subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations'
            )
            
            # Update database
            await self._update_subscription_from_stripe(db, user, updated_subscription)
            
            return {"status": "updated", "subscription": updated_subscription}
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription update error: {e}")
            raise Exception(f"Failed to update subscription: {str(e)}")
    
    async def cancel_subscription(
        self,
        db: Session,
        user: User,
        at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel user subscription."""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise Exception("No active subscription found")
            
            if at_period_end:
                # Cancel at period end
                updated_subscription = stripe.Subscription.modify(
                    user.subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            else:
                # Cancel immediately
                updated_subscription = stripe.Subscription.cancel(
                    user.subscription.stripe_subscription_id
                )
            
            # Update database
            await self._update_subscription_from_stripe(db, user, updated_subscription)
            
            return {"status": "cancelled", "at_period_end": at_period_end}
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription cancellation error: {e}")
            raise Exception(f"Failed to cancel subscription: {str(e)}")
    
    async def create_billing_portal_session(
        self,
        user: User,
        return_url: str
    ) -> str:
        """Create Stripe billing portal session."""
        try:
            if not user.subscription or not user.subscription.stripe_customer_id:
                raise Exception("No Stripe customer found")
            
            session = stripe.billing_portal.Session.create(
                customer=user.subscription.stripe_customer_id,
                return_url=return_url
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe billing portal error: {e}")
            raise Exception(f"Failed to create billing portal: {str(e)}")
    
    async def handle_webhook(
        self,
        payload: str,
        signature: str,
        db: Session
    ) -> Dict[str, Any]:
        """Handle Stripe webhook."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            logger.info(f"Stripe webhook received: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'customer.subscription.created':
                await self._handle_subscription_created(db, event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                await self._handle_subscription_updated(db, event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                await self._handle_subscription_deleted(db, event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(db, event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                await self._handle_payment_failed(db, event['data']['object'])
            
            return {"status": "success", "event_type": event['type']}
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise Exception("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise Exception("Invalid signature")
        except Exception as e:
            logger.error(f"Webhook handling error: {e}")
            raise Exception(f"Webhook processing failed: {str(e)}")
    
    def _get_price_id(self, tier: SubscriptionTier) -> Optional[str]:
        """Get Stripe price ID for subscription tier."""
        # In production, these would be actual Stripe price IDs
        price_ids = {
            SubscriptionTier.PREMIUM: "price_premium_monthly"  # Replace with actual Stripe price ID
        }
        return price_ids.get(tier)
    
    async def _update_subscription_from_stripe(
        self,
        db: Session,
        user: User,
        stripe_subscription: Any
    ) -> None:
        """Update local subscription from Stripe data."""
        try:
            if not user.subscription:
                # Create new subscription record
                subscription = Subscription(user_id=user.id)
                db.add(subscription)
                db.flush()
                user.subscription = subscription
            
            # Update subscription fields
            subscription = user.subscription
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.status = self._map_stripe_status(stripe_subscription.status)
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end
            )
            subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end
            
            # Update tier based on metadata
            tier_metadata = stripe_subscription.metadata.get('tier', 'premium')
            subscription.tier = SubscriptionTier(tier_metadata)
            
            # Set premium limits
            if subscription.tier == SubscriptionTier.PREMIUM:
                subscription.monthly_video_minutes_limit = -1  # Unlimited
                subscription.concurrent_uploads_limit = 5
                subscription.max_video_duration_seconds = -1  # Unlimited
                subscription.max_export_quality = "4K"
                subscription.watermark_enabled = False
                subscription.priority_processing = True
                subscription.advanced_ai_features = True
            
            db.commit()
            logger.info(f"Subscription updated for user {user.id}: {subscription.tier.value}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating subscription from Stripe: {e}")
            raise
    
    def _map_stripe_status(self, stripe_status: str) -> SubscriptionStatus:
        """Map Stripe subscription status to local enum."""
        status_mapping = {
            "active": SubscriptionStatus.ACTIVE,
            "canceled": SubscriptionStatus.CANCELLED,
            "incomplete": SubscriptionStatus.INACTIVE,
            "incomplete_expired": SubscriptionStatus.CANCELLED,
            "past_due": SubscriptionStatus.PAST_DUE,
            "unpaid": SubscriptionStatus.PAST_DUE,
            "trialing": SubscriptionStatus.ACTIVE
        }
        return status_mapping.get(stripe_status, SubscriptionStatus.INACTIVE)
    
    async def _handle_subscription_created(self, db: Session, subscription_data: Any):
        """Handle subscription created webhook."""
        user_id = subscription_data.metadata.get('user_id')
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                await self._update_subscription_from_stripe(db, user, subscription_data)
    
    async def _handle_subscription_updated(self, db: Session, subscription_data: Any):
        """Handle subscription updated webhook."""
        user_id = subscription_data.metadata.get('user_id')
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                await self._update_subscription_from_stripe(db, user, subscription_data)
    
    async def _handle_subscription_deleted(self, db: Session, subscription_data: Any):
        """Handle subscription deleted webhook."""
        user_id = subscription_data.metadata.get('user_id')
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user and user.subscription:
                # Downgrade to free tier
                user.subscription.tier = SubscriptionTier.FREE
                user.subscription.status = SubscriptionStatus.CANCELLED
                user.subscription.monthly_video_minutes_limit = 10.0
                user.subscription.concurrent_uploads_limit = 1
                user.subscription.max_video_duration_seconds = 60
                user.subscription.max_export_quality = "720p"
                user.subscription.watermark_enabled = True
                user.subscription.priority_processing = False
                user.subscription.advanced_ai_features = False
                db.commit()
                logger.info(f"User {user_id} downgraded to free tier")
    
    async def _handle_payment_succeeded(self, db: Session, invoice_data: Any):
        """Handle payment succeeded webhook."""
        customer_id = invoice_data.customer
        amount = invoice_data.amount_paid / 100  # Convert from cents
        
        # Find user by customer ID
        subscription = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()
        
        if subscription:
            # Record payment
            payment = PaymentHistory(
                user_id=subscription.user_id,
                stripe_invoice_id=invoice_data.id,
                amount=amount,
                currency=invoice_data.currency.upper(),
                status=PaymentStatus.COMPLETED,
                billing_period_start=datetime.fromtimestamp(
                    invoice_data.period_start
                ) if invoice_data.period_start else None,
                billing_period_end=datetime.fromtimestamp(
                    invoice_data.period_end
                ) if invoice_data.period_end else None,
                description=f"Subscription payment for {subscription.tier.value} tier"
            )
            
            db.add(payment)
            db.commit()
            
            # Send confirmation email and admin notification
            user = db.query(User).filter(User.id == subscription.user_id).first()
            if user:
                try:
                    email_service.send_subscription_confirmation(
                        user_email=user.email,
                        user_name=user.full_name or user.email.split('@')[0],
                        tier=subscription.tier.value,
                        amount=amount
                    )
                    
                    email_service.send_payment_success_notification(
                        user_email=user.email,
                        amount=amount,
                        tier=subscription.tier.value
                    )
                except Exception as email_error:
                    logger.warning(f"Failed to send payment success emails: {email_error}")
            
            logger.info(f"Payment recorded: ${amount} for user {subscription.user_id}")
    
    async def _handle_payment_failed(self, db: Session, invoice_data: Any):
        """Handle payment failed webhook."""
        customer_id = invoice_data.customer
        amount = invoice_data.amount_due / 100
        
        # Find user by customer ID
        subscription = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()
        
        if subscription:
            # Record failed payment
            payment = PaymentHistory(
                user_id=subscription.user_id,
                stripe_invoice_id=invoice_data.id,
                amount=amount,
                currency=invoice_data.currency.upper(),
                status=PaymentStatus.FAILED,
                description=f"Failed payment for {subscription.tier.value} tier"
            )
            
            db.add(payment)
            
            # Update subscription status
            subscription.status = SubscriptionStatus.PAST_DUE
            
            db.commit()
            
            # Send payment failed email
            user = db.query(User).filter(User.id == subscription.user_id).first()
            if user:
                try:
                    email_service.send_payment_failed(
                        user_email=user.email,
                        user_name=user.full_name or user.email.split('@')[0],
                        amount=amount
                    )
                    
                    # Send admin alert
                    email_service.send_system_alert(
                        alert_type="Payment Failed",
                        message=f"Payment failed for user {user.email}: ${amount}",
                        severity="warning"
                    )
                except Exception as email_error:
                    logger.warning(f"Failed to send payment failed emails: {email_error}")
            
            logger.warning(f"Payment failed: ${amount} for user {subscription.user_id}")


# Global instance
stripe_service = StripeService()