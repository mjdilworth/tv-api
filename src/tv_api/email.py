"""Email sending utilities for magic link authentication."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from tv_api.config import get_settings

logger = logging.getLogger(__name__)


def create_magic_link_email_html(
    magic_link_url: str,
    device_model: str | None,
    device_manufacturer: str | None,
    device_id: str,
) -> str:
    """Create HTML email body for magic link."""
    
    device_id_short = device_id[:8] if len(device_id) > 8 else device_id
    device_model_display = device_model or "Unknown Device"
    device_manufacturer_display = device_manufacturer or "Unknown Manufacturer"
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .button {{ 
      display: inline-block; 
      padding: 12px 24px; 
      background-color: #4A90E2; 
      color: white; 
      text-decoration: none; 
      border-radius: 4px; 
      margin: 20px 0;
    }}
    .device-info {{ 
      background-color: #f5f5f5; 
      padding: 10px; 
      border-radius: 4px; 
      margin: 10px 0;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h2>Sign in to dil.map</h2>
    
    <p>Hi there!</p>
    
    <p>Click the button below to sign in to dil.map on your Android TV:</p>
    
    <a href="{magic_link_url}" class="button">Sign In to Your TV</a>
    
    <p>Or copy and paste this link into your browser:</p>
    <p><code>{magic_link_url}</code></p>
    
    <div class="device-info">
      <strong>Device Information:</strong><br>
      Model: {device_model_display}<br>
      Manufacturer: {device_manufacturer_display}<br>
      Device ID: {device_id_short}...
    </div>
    
    <p><small>This link will expire in 15 minutes and can only be used once.</small></p>
    
    <p><small>If you didn't request this, you can safely ignore this email.</small></p>
    
    <hr>
    <p><small>dil.map by Dilworth Creative LLC<br>
    <a href="https://lucindadilworth.com">lucindadilworth.com</a></small></p>
  </div>
</body>
</html>"""


def create_magic_link_email_text(
    magic_link_url: str,
    device_model: str | None,
    device_manufacturer: str | None,
    device_id: str,
) -> str:
    """Create plain text email body for magic link."""
    
    device_id_short = device_id[:8] if len(device_id) > 8 else device_id
    device_model_display = device_model or "Unknown Device"
    device_manufacturer_display = device_manufacturer or "Unknown Manufacturer"
    
    return f"""Sign in to dil.map

Hi there!

Click the link below to sign in to dil.map on your Android TV:

{magic_link_url}

Device Information:
Model: {device_model_display}
Manufacturer: {device_manufacturer_display}
Device ID: {device_id_short}...

This link will expire in 15 minutes and can only be used once.

If you didn't request this, you can safely ignore this email.

---
dil.map by Dilworth Creative LLC
https://lucindadilworth.com
"""


async def send_magic_link_email(
    to_email: str,
    magic_link_url: str,
    device_model: str | None = None,
    device_manufacturer: str | None = None,
    device_id: str = "",
) -> bool:
    """Send magic link email to user.
    
    Args:
        to_email: Recipient email address
        magic_link_url: The magic link URL to include in the email
        device_model: Device model name
        device_manufacturer: Device manufacturer name
        device_id: Device ID
        
    Returns:
        True if email sent successfully, False otherwise
    """
    settings = get_settings()
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = "Sign in to dil.map on your TV"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    
    # Create plain text and HTML versions
    text_content = create_magic_link_email_text(
        magic_link_url, device_model, device_manufacturer, device_id
    )
    html_content = create_magic_link_email_html(
        magic_link_url, device_model, device_manufacturer, device_id
    )
    
    # Attach both versions
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    message.attach(part1)
    message.attach(part2)
    
    try:
        # Debug logging
        logger.info(f"Attempting to send email via {settings.smtp_host}:{settings.smtp_port} as {settings.smtp_username}")
        
        # Determine if we need TLS based on port and username
        use_auth = bool(settings.smtp_username and settings.smtp_password)
        use_starttls = settings.smtp_port == 587
        
        # Send email via SMTP
        if use_auth:
            # Authenticated SMTP (Gmail, etc.) - use STARTTLS
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=False,
                start_tls=True,
            )
        else:
            # Unauthenticated local SMTP - no TLS
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
            )
        
        logger.info(f"Magic link email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send magic link email to {to_email}: {e}")
        return False
