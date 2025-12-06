# Magic Link Authentication - Setup Guide

## Overview

This implementation provides magic link authentication for the TV API, allowing users to authenticate via email without passwords. The system sends a time-limited magic link to the user's email, which they can click to verify their identity and sign in.

## Installation

### 1. Install Dependencies

Run the following command to install the new dependencies:

```bash
poetry install
```

Or if you prefer to update the lock file first:

```bash
poetry lock
poetry install
```

### 2. Update Database Schema

Apply the new database schema that includes the `magic_links` table:

```bash
./scripts/recreate_database.sh
```

Or manually run:

```bash
psql -d tv_api -f db/schema.sql
```

### 3. Configure Environment Variables

Create or update your `.env` file with the following configuration:

```bash
# Database Configuration
TV_API_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tv_api

# SMTP Email Configuration
TV_API_SMTP_HOST=smtp.gmail.com
TV_API_SMTP_PORT=587
TV_API_SMTP_USERNAME=your-email@gmail.com
TV_API_SMTP_PASSWORD=your-app-password
TV_API_SMTP_FROM_EMAIL=noreply@dilly.cloud
TV_API_SMTP_FROM_NAME=dil.map

# Magic Link Configuration
TV_API_MAGIC_LINK_BASE_URL=https://tv.dilly.cloud/api/auth/verify
TV_API_MAGIC_LINK_EXPIRY_MINUTES=15

# Rate Limiting
TV_API_RATE_LIMIT_PER_EMAIL_PER_HOUR=3
TV_API_RATE_LIMIT_PER_IP_PER_HOUR=10
```

### 4. Configure SMTP Email Service

#### Option 1: Gmail (Recommended for Development)

1. Enable 2-factor authentication on your Google account
2. Generate an "App Password" from Google Account settings
3. Use the app password as `TV_API_SMTP_PASSWORD`

#### Option 2: SendGrid

```bash
TV_API_SMTP_HOST=smtp.sendgrid.net
TV_API_SMTP_PORT=587
TV_API_SMTP_USERNAME=apikey
TV_API_SMTP_PASSWORD=your-sendgrid-api-key
```

#### Option 3: AWS SES

```bash
TV_API_SMTP_HOST=email-smtp.us-east-1.amazonaws.com
TV_API_SMTP_PORT=587
TV_API_SMTP_USERNAME=your-ses-smtp-username
TV_API_SMTP_PASSWORD=your-ses-smtp-password
```

## API Endpoints

### 1. Request Magic Link

**Endpoint:** `POST /auth/magic-link`

Generates and sends a magic link to the user's email.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "deviceId": "abc123def456",
    "deviceModel": "SHIELD Android TV",
    "deviceManufacturer": "NVIDIA",
    "platform": "android-tv"
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Magic link sent! Check your email to complete sign in."
}
```

**Error Responses:**
- `400 Bad Request`: Invalid email address
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Failed to send email

### 2. Verify Magic Link

**Endpoint:** `GET /auth/verify`

Verifies the magic link token and returns user information.

**Request:**
```bash
curl "http://localhost:8000/auth/verify?token=YOUR_TOKEN&deviceId=abc123def456"
```

**Response (200 OK):**
```json
{
  "email": "user@example.com",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "deviceId": "abc123def456"
}
```

**Error Responses:**
- `400 Bad Request`: Missing required parameters
- `401 Unauthorized`: Invalid or expired magic link
- `401 Unauthorized`: Device mismatch
- `410 Gone`: Magic link already used

## Database Schema

The implementation adds a new `magic_links` table:

```sql
CREATE TABLE magic_links (
    magic_link_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token               TEXT NOT NULL UNIQUE,
    email               CITEXT NOT NULL,
    device_id           TEXT NOT NULL,
    device_model        TEXT,
    device_manufacturer TEXT,
    platform            TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    used                BOOLEAN DEFAULT FALSE,
    used_at             TIMESTAMPTZ
);
```

## Security Features

1. **Secure Token Generation**: Uses `secrets.token_urlsafe(32)` for cryptographically secure tokens
2. **Time-Limited**: Magic links expire after 15 minutes (configurable)
3. **One-Time Use**: Tokens are marked as used after verification
4. **Device Binding**: Tokens are tied to specific device IDs
5. **Rate Limiting**: 
   - 3 requests per email per hour
   - 10 requests per IP per hour
6. **Email Validation**: Automatic validation via Pydantic EmailStr

## Testing

### Manual Testing

1. Start the application:
```bash
poetry run uvicorn tv_api.main:app --reload
```

2. Request a magic link:
```bash
curl -X POST http://localhost:8000/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "deviceId": "test-device-123",
    "deviceModel": "Test Device",
    "deviceManufacturer": "Test Manufacturer"
  }'
```

3. Check your email for the magic link

4. Extract the token from the URL and verify:
```bash
curl "http://localhost:8000/auth/verify?token=YOUR_TOKEN&deviceId=test-device-123"
```

### View API Documentation

Visit `http://localhost:8000/docs` to see the interactive API documentation (Swagger UI).

## Production Considerations

### 1. Rate Limiting
The current implementation uses in-memory rate limiting, which resets on server restart. For production:
- Consider using Redis for distributed rate limiting
- Implement more sophisticated rate limiting strategies

### 2. Email Delivery
- Monitor email delivery rates and bounce rates
- Set up proper SPF, DKIM, and DMARC records
- Consider using a dedicated email service (SendGrid, AWS SES, etc.)

### 3. Database Connection Pooling
The current implementation uses asyncpg connection pooling with:
- Min size: 2 connections
- Max size: 10 connections

Adjust these values based on your production load.

### 4. Token Cleanup
Implement a background job to clean up expired magic links:

```sql
DELETE FROM magic_links 
WHERE expires_at < NOW() - INTERVAL '24 hours';
```

### 5. Monitoring and Logging
- Monitor magic link request/verification rates
- Set up alerts for high failure rates
- Track email delivery success rates

## Troubleshooting

### Email Not Sending

1. Check SMTP credentials are correct
2. Verify SMTP host and port
3. Check server logs for error messages
4. Test SMTP connection manually:

```python
import asyncio
from tv_api.email import send_magic_link_email

asyncio.run(send_magic_link_email(
    "your-email@example.com",
    "https://example.com/verify?token=test",
    "Test Device",
    "Test Manufacturer",
    "test-123"
))
```

### Database Connection Issues

1. Verify database is running
2. Check DATABASE_URL is correct
3. Ensure database schema is up to date
4. Check database logs for connection errors

### Rate Limiting Issues

If you're hitting rate limits during testing:
1. Adjust `TV_API_RATE_LIMIT_PER_EMAIL_PER_HOUR` and `TV_API_RATE_LIMIT_PER_IP_PER_HOUR`
2. Or restart the server to clear in-memory rate limits

## File Structure

```
src/tv_api/
├── api/
│   └── routers/
│       └── auth.py          # Magic link endpoints
├── config.py                # Configuration with email/DB settings
├── database.py              # Database connection management
├── email.py                 # Email sending utilities
└── main.py                  # Application setup with DB lifecycle

db/
└── schema.sql               # Updated with magic_links table
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TV_API_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/tv_api` | PostgreSQL connection string |
| `TV_API_SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `TV_API_SMTP_PORT` | `587` | SMTP server port |
| `TV_API_SMTP_USERNAME` | `""` | SMTP username |
| `TV_API_SMTP_PASSWORD` | `""` | SMTP password |
| `TV_API_SMTP_FROM_EMAIL` | `noreply@dilly.cloud` | From email address |
| `TV_API_SMTP_FROM_NAME` | `dil.map` | From name |
| `TV_API_MAGIC_LINK_BASE_URL` | `https://tv.dilly.cloud/api/auth/verify` | Base URL for magic links |
| `TV_API_MAGIC_LINK_EXPIRY_MINUTES` | `15` | Magic link expiry time |
| `TV_API_RATE_LIMIT_PER_EMAIL_PER_HOUR` | `3` | Max requests per email |
| `TV_API_RATE_LIMIT_PER_IP_PER_HOUR` | `10` | Max requests per IP |

## Support

For questions or issues, refer to the original specification in `MAGIC_LINK_SERVER_API.md`.
