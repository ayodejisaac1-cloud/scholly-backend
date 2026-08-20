import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = settings.SMTP_EMAIL
        self.sender_password = settings.SMTP_PASSWORD

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email using Gmail SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add plain text version if provided
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # Connect to Gmail SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    def send_verification_email(self, to_email: str, name: str, token: str) -> bool:
        """Send email verification link"""
        subject = "Verify Your Scholly Account"
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #2563EB; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>Welcome to Scholly, {name}!</h2>
                    <p>Thank you for registering your school with Scholly. To get started, please verify your email address.</p>
                    <div style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify Email Address</a>
                    </div>
                    <p style="color: #666; font-size: 14px;">This link will expire in 24 hours.</p>
                    <p style="color: #666; font-size: 14px;">If you didn't register, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                    <p>This email was sent to {to_email}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Scholly, {name}!
        
        Thank you for registering your school with Scholly. To get started, please verify your email address by clicking the link below:
        
        {verification_url}
        
        This link will expire in 24 hours.
        
        If you didn't register, please ignore this email.
        
        ---
        © 2024 Scholly. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)

    def send_welcome_email(self, to_email: str, name: str, school_name: str) -> bool:
        """Send welcome email after verification"""
        subject = f"Welcome to Scholly, {name}!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }}
                .feature {{ padding: 15px; margin: 10px 0; background: white; border-radius: 5px; border-left: 4px solid #2563EB; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #2563EB; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>Welcome to Scholly, {name}!</h2>
                    <p>Your school <strong>{school_name}</strong> has been successfully set up!</p>
                    
                    <h3>What's Next?</h3>
                    <div class="feature">
                        <strong>📋 Complete Your Profile</strong>
                        <p>Add your school logo, contact details, and customize your settings.</p>
                    </div>
                    <div class="feature">
                        <strong>👨‍🎓 Add Students</strong>
                        <p>Start adding students and setting up their fee structures.</p>
                    </div>
                    <div class="feature">
                        <strong>👥 Invite Team Members</strong>
                        <p>Invite admins and teachers to help manage your school.</p>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{settings.FRONTEND_URL}/dashboard" class="button">Go to Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                    <p>This email was sent to {to_email}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Scholly, {name}!
        
        Your school {school_name} has been successfully set up!
        
        What's Next?
        ------------
        📋 Complete Your Profile
        Add your school logo, contact details, and customize your settings.
        
        👨‍🎓 Add Students
        Start adding students and setting up their fee structures.
        
        👥 Invite Team Members
        Invite admins and teachers to help manage your school.
        
        Go to Dashboard: {settings.FRONTEND_URL}/dashboard
        
        ---
        © 2024 Scholly. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)

    def send_invitation_email(
        self, 
        to_email: str, 
        inviter_name: str, 
        school_name: str, 
        role: str,
        token: str
    ) -> bool:
        """Send team invitation email"""
        subject = f"You've been invited to join {school_name} on Scholly"
        accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #2563EB; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .info-box {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; border: 1px solid #e0e0e0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>You're Invited!</h2>
                    <p><strong>{inviter_name}</strong> has invited you to join <strong>{school_name}</strong> as a <strong>{role}</strong>.</p>
                    
                    <div class="info-box">
                        <p><strong>What you'll be able to do:</strong></p>
                        <ul>
                            <li>Manage students and their records</li>
                            <li>Record and track payments</li>
                            <li>Generate financial reports</li>
                            <li>And much more...</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{accept_url}" class="button">Accept Invitation</a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">This invitation will expire in 7 days.</p>
                    <p style="color: #666; font-size: 14px;">If you weren't expecting this, you can ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                    <p>This email was sent to {to_email}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        You're Invited!
        
        {inviter_name} has invited you to join {school_name} as a {role}.
        
        What you'll be able to do:
        - Manage students and their records
        - Record and track payments
        - Generate financial reports
        - And much more...
        
        Accept Invitation: {accept_url}
        
        This invitation will expire in 7 days.
        If you weren't expecting this, you can ignore this email.
        
        ---
        © 2024 Scholly. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)

    def send_password_reset_email(self, to_email: str, name: str, token: str) -> bool:
        """Send password reset email"""
        subject = "Reset Your Scholly Password"
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #2563EB; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>Password Reset Request</h2>
                    <p>Hello {name},</p>
                    <p>We received a request to reset your Scholly password. Click the button below to create a new password.</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
                    <p style="color: #666; font-size: 14px;">If you didn't request this, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                    <p>This email was sent to {to_email}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        Hello {name},
        
        We received a request to reset your Scholly password. Click the link below to create a new password:
        
        {reset_url}
        
        This link will expire in 1 hour.
        If you didn't request this, please ignore this email.
        
        ---
        © 2024 Scholly. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)

    def send_school_approval_email(self, to_email: str, school_name: str, status: str) -> bool:
        """Send school approval/rejection email"""
        subject = f"School {status.title()}: {school_name}"
        
        status_emoji = "✅" if status == "active" else "❌"
        status_message = "approved and activated" if status == "active" else "suspended"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ color: white; margin: 0; }}
                .content {{ padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #2563EB; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>{status_emoji} School {status.title()}</h2>
                    <p>Your school <strong>{school_name}</strong> has been {status_message}.</p>
                    
                    {status == "active" and """
                    <p>You can now log in and start using all the features of Scholly!</p>
                    <div style="text-align: center;">
                        <a href="{settings.FRONTEND_URL}/login" class="button">Login to Dashboard</a>
                    </div>
                    ''' if status == "active" else '''
                    <p>If you have any questions, please contact support.</p>
                    '''}
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                    <p>This email was sent to {to_email}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)

    def send_test_email(self, to_email: str) -> bool:
        """Send a test email to verify configuration"""
        subject = "Scholly Email Test"
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #2563EB; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }
                .header h1 { color: white; margin: 0; }
                .content { padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px; }
                .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 Scholly</h1>
                </div>
                <div class="content">
                    <h2>Email Test Successful! ✅</h2>
                    <p>Your Scholly email configuration is working correctly.</p>
                    <p>You will now receive notifications for:</p>
                    <ul>
                        <li>School registrations</li>
                        <li>Team invitations</li>
                        <li>Password resets</li>
                        <li>School approvals</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Scholly. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
