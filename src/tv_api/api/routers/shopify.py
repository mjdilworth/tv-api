"""Shopify webhook endpoints."""

from __future__ import annotations

import hmac
import hashlib
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from tv_api.config import get_settings
from tv_api.database import get_db_connection
from tv_api.logging import get_logger

router = APIRouter(prefix="/shopify", tags=["shopify"])
logger = get_logger("shopify")


class ShopifyCustomer(BaseModel):
    """Shopify customer data from webhook."""
    
    id: int
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    created_at: str
    updated_at: str


class WebhookResponse(BaseModel):
    """Response from webhook processing."""
    
    success: bool
    message: str
    user_id: str | None = None


def verify_shopify_webhook(
    body: bytes,
    hmac_header: str | None,
    secret: str,
) -> bool:
    """Verify Shopify webhook signature using HMAC-SHA256.
    
    Args:
        body: Raw request body bytes
        hmac_header: X-Shopify-Hmac-SHA256 header value (base64 encoded)
        secret: Shopify webhook secret
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not hmac_header or not secret:
        return False
    
    # Compute HMAC-SHA256 of the body
    computed_hmac = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    
    # Shopify sends the HMAC as base64
    import base64
    try:
        provided_hmac = base64.b64decode(hmac_header)
        return hmac.compare_digest(computed_hmac, provided_hmac)
    except Exception:
        return False


@router.post("/webhooks/customers/create", summary="Handle Shopify customer creation")
async def handle_customer_create(
    request: Request,
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
    x_shopify_hmac_sha256: Annotated[str | None, Header()] = None,
    x_shopify_topic: Annotated[str | None, Header()] = None,
    x_shopify_shop_domain: Annotated[str | None, Header()] = None,
) -> WebhookResponse:
    """Handle Shopify customers/create webhook.
    
    When a customer is created in Shopify, this webhook:
    1. Verifies the webhook signature
    2. Creates or updates the user in the database
    3. Returns the user_id
    
    Shopify API version: 2025-10
    """
    
    settings = get_settings()
    
    # Get raw body for HMAC verification
    body = await request.body()
    
    # Verify webhook signature
    if not verify_shopify_webhook(body, x_shopify_hmac_sha256, settings.shopify_webhook_secret):
        logger.warning(
            f"Invalid Shopify webhook signature from {x_shopify_shop_domain}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    logger.info(
        f"Received Shopify webhook: topic={x_shopify_topic} "
        f"shop={x_shopify_shop_domain}"
    )
    
    # Parse JSON body
    try:
        data = await request.json()
        customer = ShopifyCustomer(**data)
    except Exception as e:
        logger.error(f"Failed to parse Shopify customer data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer data"
        )
    
    # Validate email exists
    if not customer.email:
        logger.warning(f"Shopify customer {customer.id} has no email address")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer email is required"
        )
    
    # Create or update user in database
    try:
        async with conn.cursor() as cur:
            # Check if user exists
            await cur.execute(
                """
                SELECT user_id FROM tv_app.users WHERE email = %s
                """,
                (customer.email,),
            )
            existing_user = await cur.fetchone()
            
            if existing_user:
                # Update display name if we have first/last name
                display_name = None
                if customer.first_name or customer.last_name:
                    display_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                
                if display_name:
                    await cur.execute(
                        """
                        UPDATE tv_app.users
                        SET display_name = %s
                        WHERE email = %s
                        RETURNING user_id
                        """,
                        (display_name, customer.email),
                    )
                    user = await cur.fetchone()
                else:
                    user = existing_user
                
                logger.info(
                    f"Updated existing user {user['user_id']} from Shopify customer {customer.id}"
                )
            else:
                # Create new user
                display_name = None
                if customer.first_name or customer.last_name:
                    display_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                
                await cur.execute(
                    """
                    INSERT INTO tv_app.users (email, display_name)
                    VALUES (%s, %s)
                    RETURNING user_id
                    """,
                    (customer.email, display_name),
                )
                user = await cur.fetchone()
                
                logger.info(
                    f"Created new user {user['user_id']} from Shopify customer {customer.id}"
                )
        
        return WebhookResponse(
            success=True,
            message=f"User created/updated successfully",
            user_id=str(user["user_id"])
        )
    
    except Exception as e:
        logger.error(f"Error processing Shopify customer webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process customer"
        )
