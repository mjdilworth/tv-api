"""Authentication endpoints for magic link functionality."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr

from tv_api.config import get_settings
from tv_api.database import get_db_connection
from tv_api.email import send_magic_link_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# Request/Response Models
class MagicLinkRequest(BaseModel):
    """Request payload for magic link generation."""

    email: EmailStr
    deviceId: str
    deviceModel: str | None = None
    deviceManufacturer: str | None = None
    platform: str | None = "android-tv"


class MagicLinkResponse(BaseModel):
    """Response for magic link request."""

    success: bool
    message: str


class VerifyResponse(BaseModel):
    """Response for magic link verification."""

    email: str
    userId: str
    deviceId: str


class AuthStatusResponse(BaseModel):
    """Response for authentication status check."""

    authenticated: bool
    email: str | None = None
    userId: str | None = None
    deviceId: str | None = None


class LogoutResponse(BaseModel):
    """Response for logout request."""

    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    message: str


# Rate limiting helper (simple in-memory implementation)
# For production, consider using Redis
rate_limit_store: dict[str, list[datetime]] = {}


def check_rate_limit(key: str, limit: int, window_hours: int = 1) -> bool:
    """Check if rate limit has been exceeded.
    
    Args:
        key: Rate limit key (e.g., email or IP)
        limit: Maximum number of requests allowed
        window_hours: Time window in hours
        
    Returns:
        True if request is allowed, False if rate limit exceeded
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=window_hours)
    
    # Clean up old entries
    if key in rate_limit_store:
        rate_limit_store[key] = [
            timestamp for timestamp in rate_limit_store[key] 
            if timestamp > cutoff
        ]
    else:
        rate_limit_store[key] = []
    
    # Check limit
    if len(rate_limit_store[key]) >= limit:
        return False
    
    # Add new entry
    rate_limit_store[key].append(now)
    return True


@router.post(
    "/magic-link",
    summary="Request magic link",
    response_model=MagicLinkResponse,
    responses={
        200: {"description": "Magic link sent successfully"},
        400: {"model": ErrorResponse, "description": "Invalid email address"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
        500: {"model": ErrorResponse, "description": "Failed to send magic link"},
    },
)
async def request_magic_link(
    payload: MagicLinkRequest,
    request: Request,
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> MagicLinkResponse:
    """Generate a magic link and send it to the user's email address.
    
    This endpoint:
    1. Validates the email format (handled by Pydantic)
    2. Checks rate limits
    3. Generates a unique secure token
    4. Stores the magic link in the database
    5. Sends the email with the magic link
    """
    settings = get_settings()
    
    # Rate limiting by email
    email_key = f"email:{payload.email.lower()}"
    if not check_rate_limit(email_key, settings.rate_limit_per_email_per_hour):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    
    # Rate limiting by IP
    client_ip = request.client.host if request.client else "unknown"
    ip_key = f"ip:{client_ip}"
    if not check_rate_limit(ip_key, settings.rate_limit_per_ip_per_hour):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    
    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.magic_link_expiry_minutes
    )
    
    try:
        # Store magic link in database
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO tv_app.magic_links 
                    (token, email, device_id, device_model, device_manufacturer, 
                     platform, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    token,
                    payload.email.lower(),
                    payload.deviceId,
                    payload.deviceModel,
                    payload.deviceManufacturer,
                    payload.platform,
                    expires_at,
                ),
            )
        
        # Create magic link URL
        magic_link_url = f"{settings.magic_link_base_url}?token={token}&deviceId={payload.deviceId}"
        
        # Send email
        email_sent = await send_magic_link_email(
            to_email=payload.email,
            magic_link_url=magic_link_url,
            device_model=payload.deviceModel,
            device_manufacturer=payload.deviceManufacturer,
            device_id=payload.deviceId,
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send magic link",
            )
        
        return MagicLinkResponse(
            success=True,
            message="Magic link sent! Check your email to complete sign in.",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating magic link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send magic link",
        )


@router.get(
    "/verify",
    summary="Verify magic link",
    responses={
        200: {"description": "Magic link verified successfully", "content": {"text/html": {}}},
        400: {"description": "Missing required parameters"},
        401: {"description": "Invalid or expired magic link"},
        410: {"description": "Magic link already used"},
    },
)
async def verify_magic_link(
    token: Annotated[str, Query(description="Magic link token")],
    deviceId: Annotated[str, Query(description="Device ID")],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> HTMLResponse:
    """Verify the magic link token and return user information.
    
    This endpoint:
    1. Validates the token and device ID
    2. Checks if the token has expired
    3. Verifies the device ID matches
    4. Checks if the token has already been used
    5. Marks the token as used
    6. Creates or retrieves the user
    7. Returns user information
    """
    
    # Find the magic link
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT magic_link_id, token, email, device_id, expires_at, used, used_at
            FROM tv_app.magic_links
            WHERE token = %s
            """,
            (token,),
        )
        magic_link = await cur.fetchone()
    
    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )
    
    # Check if expired
    if datetime.now(timezone.utc) > magic_link["expires_at"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )
    
    # Check if already used
    if magic_link["used"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This magic link has already been used",
        )
    
    # Verify device ID matches
    if magic_link["device_id"] != deviceId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This link was issued for a different device",
        )
    
    try:
        async with conn.cursor() as cur:
            # Mark token as used
            await cur.execute(
                """
                UPDATE tv_app.magic_links
                SET used = TRUE, used_at = NOW()
                WHERE token = %s
                """,
                (token,),
            )
            
            # Get or create user
            await cur.execute(
                """
                SELECT user_id, email
                FROM tv_app.users
                WHERE email = %s
                """,
                (magic_link["email"],),
            )
            user = await cur.fetchone()
            
            if not user:
                # Create new user
                await cur.execute(
                    """
                    INSERT INTO tv_app.users (email)
                    VALUES (%s)
                    RETURNING user_id, email
                    """,
                    (magic_link["email"],),
                )
                user = await cur.fetchone()
        
        logger.info(
            f"Magic link verified successfully for user {user['user_id']} "
            f"on device {deviceId}"
        )
        
        # Return HTML success page
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In Successful - dil.map</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            text-align: center;
            max-width: 500px;
        }}
        .success-icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
        }}
        h1 {{
            color: #2d3748;
            margin: 0 0 1rem;
            font-size: 2rem;
        }}
        p {{
            color: #4a5568;
            font-size: 1.1rem;
            line-height: 1.6;
            margin: 0.5rem 0;
        }}
        .email {{
            color: #667eea;
            font-weight: 600;
        }}
        .device {{
            background: #f7fafc;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 1.5rem;
            font-size: 0.9rem;
            color: #718096;
        }}
        .footer {{
            margin-top: 2rem;
            font-size: 0.9rem;
            color: #a0aec0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✓</div>
        <h1>You're all set!</h1>
        <p>Your TV has been successfully authenticated.</p>
        <p>Signed in as <span class="email">{user["email"]}</span></p>
        <div class="device">
            Device ID: {deviceId[:12]}...
        </div>
        <div class="footer">
            You can close this window and return to your TV.
        </div>
    </div>
</body>
</html>
"""
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"Error verifying magic link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify magic link",
        )


@router.get(
    "/status",
    summary="Check authentication status",
    response_model=AuthStatusResponse,
    responses={
        200: {"description": "Authentication status returned"},
        400: {"description": "Missing device ID"},
    },
)
async def check_auth_status(
    deviceId: Annotated[str, Query(description="Device ID to check")],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> AuthStatusResponse:
    """Check if a device has been authenticated via magic link.
    
    The TV app should poll this endpoint after requesting a magic link.
    Once the user clicks the email link and verifies, this will return
    the authenticated user information.
    
    This endpoint checks for recently used (within last 5 minutes) magic links
    for the given device.
    """
    
    # Look for recently verified magic links for this device
    # Check within last 5 minutes to allow for the auth flow
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ml.email, u.user_id
            FROM tv_app.magic_links ml
            JOIN tv_app.users u ON u.email = ml.email
            WHERE ml.device_id = %s
              AND ml.used = TRUE
              AND ml.used_at > %s
            ORDER BY ml.used_at DESC
            LIMIT 1
            """,
            (deviceId, cutoff_time),
        )
        result = await cur.fetchone()
    
    if result:
        return AuthStatusResponse(
            authenticated=True,
            email=result["email"],
            userId=str(result["user_id"]),
            deviceId=deviceId,
        )
    else:
        return AuthStatusResponse(
            authenticated=False,
            deviceId=deviceId,
        )


@router.post(
    "/logout",
    summary="Log out a device",
    response_model=LogoutResponse,
    responses={
        200: {"description": "Device logged out successfully"},
        400: {"description": "Missing device ID"},
    },
)
async def logout_device(
    deviceId: Annotated[str, Query(description="Device ID to log out")],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> LogoutResponse:
    """Log out a device by invalidating all its magic links.
    
    This marks all magic links for the device as used, effectively
    logging out the device. The TV app should then clear its stored
    userId and return to the login screen.
    """
    
    try:
        async with conn.cursor() as cur:
            # Mark all magic links for this device as used
            await cur.execute(
                """
                UPDATE tv_app.magic_links
                SET used = TRUE, used_at = NOW()
                WHERE device_id = %s AND used = FALSE
                """,
                (deviceId,),
            )
            rows_updated = cur.rowcount
        
        logger.info(f"Device {deviceId} logged out, invalidated {rows_updated} magic links")
        
        return LogoutResponse(
            success=True,
            message="Device logged out successfully",
        )
        
    except Exception as e:
        logger.error(f"Error logging out device {deviceId}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log out device",
        )
