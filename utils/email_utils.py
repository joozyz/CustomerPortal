import os
from flask import url_for
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging
from models import SystemSettings

logger = logging.getLogger(__name__)

def send_password_reset_email(user, token):
    """Send password reset email to user"""
    try:
        # Get SMTP settings from database
        smtp_server = SystemSettings.get_setting('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(SystemSettings.get_setting('SMTP_PORT', '587'))
        smtp_username = SystemSettings.get_setting('SMTP_USERNAME')
        smtp_password = SystemSettings.get_setting('SMTP_PASSWORD')

        if not all([smtp_username, smtp_password]):
            logger.error("SMTP credentials not configured")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Password Reset Request"
        msg['From'] = smtp_username
        msg['To'] = user.email

        # Create reset link
        reset_url = url_for('auth.reset_password', token=token, _external=True)

        # HTML version of the email
        html = f"""
        <html>
          <body>
            <h2>Password Reset Request</h2>
            <p>Dear {user.username},</p>
            <p>To reset your password, please click the link below:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you did not request a password reset, please ignore this email.</p>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        logger.info(f"Password reset email sent to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return False