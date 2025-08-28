import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from app.core.config import settings
from app.core.logger import logger


class EmailService:
    """Email service for sending notifications and alerts."""
    
    def __init__(self):
        self.smtp_server = settings.EMAIL_HOST
        self.smtp_port = settings.EMAIL_PORT
        self.username = settings.EMAIL_USERNAME
        self.password = settings.EMAIL_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.use_tls = settings.EMAIL_USE_TLS
        
        # Setup Jinja2 for email templates
        templates_path = Path(__file__).parent.parent / "templates" / "emails"
        self.jinja_env = Environment(loader=FileSystemLoader(templates_path))
    
    def _create_smtp_connection(self):
        """Create SMTP connection with proper security."""
        try:
            if self.use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            
            if self.username and self.password:
                server.login(self.username, self.password)
            
            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {e}")
            raise
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> tuple:
        """Render email template with context."""
        try:
            template = self.jinja_env.get_template(f"{template_name}.html")
            html_content = template.render(**context)
            
            # Try to load text version
            try:
                text_template = self.jinja_env.get_template(f"{template_name}.txt")
                text_content = text_template.render(**context)
            except:
                # Fallback to basic text extraction
                import re
                text_content = re.sub('<[^<]+?>', '', html_content)
            
            return html_content, text_content
        except Exception as e:
            logger.error(f"Failed to render email template {template_name}: {e}")
            raise
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """Send email with HTML and optional text content."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Add text and HTML parts
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    with open(attachment['path'], 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment.get("name", "attachment")}'
                    )
                    msg.attach(part)
            
            # Send email
            server = self._create_smtp_connection()
            
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            server.sendmail(self.from_email, recipients, msg.as_string())
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_template_email(
        self,
        to_email: str,
        template_name: str,
        subject: str,
        context: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """Send email using template."""
        try:
            html_content, text_content = self._render_template(template_name, context)
            return self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachments=attachments,
                cc=cc,
                bcc=bcc
            )
        except Exception as e:
            logger.error(f"Failed to send template email to {to_email}: {e}")
            return False
    
    # User-related email methods
    
    def send_welcome_email(self, user_email: str, user_name: str, verification_link: str = None) -> bool:
        """Send welcome email to new user."""
        context = {
            'user_name': user_name,
            'verification_link': verification_link,
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Welcome to AIVideoMaker!"
        return self.send_template_email(
            to_email=user_email,
            template_name='welcome',
            subject=subject,
            context=context
        )
    
    def send_verification_email(self, user_email: str, user_name: str, verification_link: str) -> bool:
        """Send email verification link."""
        context = {
            'user_name': user_name,
            'verification_link': verification_link,
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Verify your AIVideoMaker account"
        return self.send_template_email(
            to_email=user_email,
            template_name='verification',
            subject=subject,
            context=context
        )
    
    def send_password_reset_email(self, user_email: str, user_name: str, reset_link: str) -> bool:
        """Send password reset email."""
        context = {
            'user_name': user_name,
            'reset_link': reset_link,
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Reset your AIVideoMaker password"
        return self.send_template_email(
            to_email=user_email,
            template_name='password_reset',
            subject=subject,
            context=context
        )
    
    # Subscription-related email methods
    
    def send_subscription_confirmation(self, user_email: str, user_name: str, tier: str, amount: float) -> bool:
        """Send subscription confirmation email."""
        context = {
            'user_name': user_name,
            'tier': tier.title(),
            'amount': amount,
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = f"Welcome to AIVideoMaker {tier.title()}!"
        return self.send_template_email(
            to_email=user_email,
            template_name='subscription_confirmation',
            subject=subject,
            context=context
        )
    
    def send_subscription_cancelled(self, user_email: str, user_name: str, end_date: datetime) -> bool:
        """Send subscription cancellation email."""
        context = {
            'user_name': user_name,
            'end_date': end_date.strftime('%B %d, %Y'),
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Your AIVideoMaker subscription has been cancelled"
        return self.send_template_email(
            to_email=user_email,
            template_name='subscription_cancelled',
            subject=subject,
            context=context
        )
    
    def send_payment_failed(self, user_email: str, user_name: str, amount: float) -> bool:
        """Send payment failure notification."""
        context = {
            'user_name': user_name,
            'amount': amount,
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Payment failed for your AIVideoMaker subscription"
        return self.send_template_email(
            to_email=user_email,
            template_name='payment_failed',
            subject=subject,
            context=context
        )
    
    def send_usage_limit_warning(self, user_email: str, user_name: str, usage_percent: int, tier: str) -> bool:
        """Send usage limit warning email."""
        context = {
            'user_name': user_name,
            'usage_percent': usage_percent,
            'tier': tier.title(),
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = f"You've used {usage_percent}% of your monthly video minutes"
        return self.send_template_email(
            to_email=user_email,
            template_name='usage_warning',
            subject=subject,
            context=context
        )
    
    def send_usage_limit_exceeded(self, user_email: str, user_name: str, tier: str) -> bool:
        """Send usage limit exceeded email."""
        context = {
            'user_name': user_name,
            'tier': tier.title(),
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Monthly video processing limit exceeded"
        return self.send_template_email(
            to_email=user_email,
            template_name='usage_exceeded',
            subject=subject,
            context=context
        )
    
    # Admin notification methods
    
    def send_admin_notification(
        self,
        subject: str,
        content: str,
        user_id: Optional[int] = None,
        severity: str = "info"
    ) -> bool:
        """Send notification to admin."""
        admin_emails = settings.ADMIN_EMAIL_ADDRESSES
        if not admin_emails:
            logger.warning("No admin email addresses configured")
            return False
        
        context = {
            'subject': subject,
            'content': content,
            'user_id': user_id,
            'severity': severity,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'app_name': 'AIVideoMaker'
        }
        
        success = True
        for admin_email in admin_emails:
            result = self.send_template_email(
                to_email=admin_email,
                template_name='admin_notification',
                subject=f"[AIVideoMaker] {subject}",
                context=context
            )
            success = success and result
        
        return success
    
    # GDPR Email Notifications
    def send_data_export_confirmation(self, user_email: str, user_name: str) -> bool:
        """Send confirmation email for data export request"""
        context = {
            'user_name': user_name,
            'request_date': datetime.now().strftime("%B %d, %Y"),
            'processing_time': "within 1 month",
            'support_email': "privacy@aivideomaker.com",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Data Export Request Confirmation - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='gdpr_export_confirmation',
            subject=subject,
            context=context
        )
    
    def send_data_export_ready(self, user_email: str, user_name: str, expires_date: datetime) -> bool:
        """Send notification when data export is ready"""
        context = {
            'user_name': user_name,
            'expires_date': expires_date.strftime("%B %d, %Y"),
            'download_url': f"{self.settings.BASE_URL}/api/gdpr/export/download",
            'support_email': "privacy@aivideomaker.com",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Your Data Export is Ready - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='gdpr_export_ready',
            subject=subject,
            context=context
        )
    
    def send_data_deletion_confirmation(self, user_email: str, user_name: str) -> bool:
        """Send confirmation email for data deletion request"""
        context = {
            'user_name': user_name,
            'request_date': datetime.now().strftime("%B %d, %Y"),
            'grace_period': "30 days",
            'support_email': "privacy@aivideomaker.com",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Data Deletion Request Confirmation - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='gdpr_deletion_confirmation',
            subject=subject,
            context=context
        )
    
    def send_data_deletion_scheduled(self, user_email: str, user_name: str, deletion_date: datetime) -> bool:
        """Send notification when data deletion is scheduled"""
        context = {
            'user_name': user_name,
            'deletion_date': deletion_date.strftime("%B %d, %Y"),
            'cancel_url': f"{self.settings.BASE_URL}/privacy/cancel-deletion",
            'support_email': "privacy@aivideomaker.com",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Data Deletion Scheduled - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='gdpr_deletion_scheduled',
            subject=subject,
            context=context
        )
    
    def send_privacy_policy_update(self, user_email: str, user_name: str, policy_version: str) -> bool:
        """Send notification about privacy policy updates"""
        context = {
            'user_name': user_name,
            'policy_version': policy_version,
            'effective_date': (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y"),
            'policy_url': f"{self.settings.BASE_URL}/privacy-policy",
            'consent_url': f"{self.settings.BASE_URL}/privacy/consent",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Important: Updated Privacy Policy - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='privacy_policy_update',
            subject=subject,
            context=context
        )
    
    def send_data_breach_notification(self, user_email: str, user_name: str, breach_details: dict) -> bool:
        """Send data breach notification to affected users"""
        context = {
            'user_name': user_name,
            'incident_date': breach_details.get("incident_date", "Unknown"),
            'data_types': breach_details.get("affected_data", []),
            'actions_taken': breach_details.get("containment_measures", ""),
            'next_steps': breach_details.get("recommended_actions", []),
            'support_email': "security@aivideomaker.com",
            'app_name': 'AIVideoMaker',
            'year': datetime.now().year
        }
        
        subject = "Important Security Notice - AIVideoMaker"
        return self.send_template_email(
            to_email=user_email,
            template_name='data_breach_notification',
            subject=subject,
            context=context
        )
    
    def send_new_user_notification(self, user_email: str, user_name: str, oauth_provider: str = None) -> bool:
        """Send new user notification to admin."""
        content = f"New user registered: {user_name} ({user_email})"
        if oauth_provider:
            content += f" via {oauth_provider}"
        
        return self.send_admin_notification(
            subject="New User Registration",
            content=content,
            severity="info"
        )
    
    def send_payment_success_notification(self, user_email: str, amount: float, tier: str) -> bool:
        """Send payment success notification to admin."""
        content = f"Payment successful: ${amount} for {tier} subscription by {user_email}"
        
        return self.send_admin_notification(
            subject="Payment Successful",
            content=content,
            severity="info"
        )
    
    def send_system_alert(self, alert_type: str, message: str, severity: str = "warning") -> bool:
        """Send system alert to admin."""
        return self.send_admin_notification(
            subject=f"System Alert: {alert_type}",
            content=message,
            severity=severity
        )


# Global email service instance
email_service = EmailService()