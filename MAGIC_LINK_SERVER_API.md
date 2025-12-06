# Magic Link API Server Implementation Guide

This document provides guidance for implementing the backend server endpoints required for magic link authentication in the dil.map Android TV app.

## Base URL
```
https://tv.dilly.cloud/api
```

## Endpoints

### 1. Request Magic Link

**Endpoint:** `POST /auth/magic-link`

**Description:** Generates a magic link and sends it to the user's email address.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "deviceId": "abc123def456...",
  "deviceModel": "SHIELD Android TV",
  "deviceManufacturer": "NVIDIA",
  "platform": "android-tv"
}
```

**Success Response (200 OK):**
```json
{
  "success": true,
  "message": "Magic link sent! Check your email to complete sign in."
}
```

**Error Responses:**

*400 Bad Request - Invalid Email:*
```json
{
  "success": false,
  "message": "Invalid email address"
}
```

*429 Too Many Requests:*
```json
{
  "success": false,
  "message": "Too many requests. Please try again later."
}
```

*500 Internal Server Error:*
```json
{
  "success": false,
  "message": "Failed to send magic link"
}
```

**Implementation Notes:**
1. Validate email format
2. Generate unique token (UUID or similar)
3. Store in database:
   - Token
   - Email
   - Device ID
   - Created timestamp
   - Expiration (recommend 15 minutes)
   - Used flag (false initially)
4. Send email with magic link URL
5. Rate limit by email/IP to prevent abuse

**Database Schema Example:**
```sql
CREATE TABLE magic_links (
  id SERIAL PRIMARY KEY,
  token VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) NOT NULL,
  device_id VARCHAR(255) NOT NULL,
  device_model VARCHAR(255),
  device_manufacturer VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL,
  used BOOLEAN DEFAULT FALSE,
  used_at TIMESTAMP
);

CREATE INDEX idx_magic_links_token ON magic_links(token);
CREATE INDEX idx_magic_links_email ON magic_links(email);
```

---

### 2. Verify Magic Link

**Endpoint:** `GET /auth/verify`

**Description:** Verifies the magic link token and returns user information.

**Query Parameters:**
- `token` (required): The unique token from the magic link
- `deviceId` (required): The device ID that requested the magic link

**Example Request:**
```
GET /auth/verify?token=550e8400-e29b-41d4-a716-446655440000&deviceId=abc123def456
```

**Success Response (200 OK):**
```json
{
  "email": "user@example.com",
  "userId": "user_123456",
  "deviceId": "abc123def456"
}
```

**Error Responses:**

*400 Bad Request - Missing Parameters:*
```json
{
  "message": "Missing required parameters"
}
```

*401 Unauthorized - Invalid Token:*
```json
{
  "message": "Invalid or expired magic link"
}
```

*401 Unauthorized - Device Mismatch:*
```json
{
  "message": "This link was issued for a different device"
}
```

*410 Gone - Already Used:*
```json
{
  "message": "This magic link has already been used"
}
```

**Implementation Notes:**
1. Validate token format
2. Query database for matching token
3. Check token hasn't expired
4. Verify device ID matches
5. Check token hasn't been used
6. Mark token as used
7. Create user session
8. Return user information
9. Optionally: create or update user record

**Verification Logic Example:**
```javascript
async function verifyMagicLink(token, deviceId) {
  // Find the magic link
  const magicLink = await db.query(
    'SELECT * FROM magic_links WHERE token = $1',
    [token]
  );
  
  if (!magicLink) {
    throw new Error('Invalid or expired magic link');
  }
  
  // Check if expired
  if (new Date() > magicLink.expires_at) {
    throw new Error('Invalid or expired magic link');
  }
  
  // Check if already used
  if (magicLink.used) {
    throw new Error('This magic link has already been used');
  }
  
  // Verify device ID
  if (magicLink.device_id !== deviceId) {
    throw new Error('This link was issued for a different device');
  }
  
  // Mark as used
  await db.query(
    'UPDATE magic_links SET used = TRUE, used_at = NOW() WHERE token = $1',
    [token]
  );
  
  // Get or create user
  let user = await db.query('SELECT * FROM users WHERE email = $1', [magicLink.email]);
  
  if (!user) {
    user = await db.query(
      'INSERT INTO users (email, created_at) VALUES ($1, NOW()) RETURNING *',
      [magicLink.email]
    );
  }
  
  // Create session or JWT token
  const session = createSession(user.id, deviceId);
  
  return {
    email: user.email,
    userId: user.id,
    deviceId: deviceId,
    sessionToken: session.token
  };
}
```

---

## Email Template

**Subject:** Sign in to dil.map on your TV

**HTML Body:**
```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .button { 
      display: inline-block; 
      padding: 12px 24px; 
      background-color: #4A90E2; 
      color: white; 
      text-decoration: none; 
      border-radius: 4px; 
      margin: 20px 0;
    }
    .device-info { 
      background-color: #f5f5f5; 
      padding: 10px; 
      border-radius: 4px; 
      margin: 10px 0;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>Sign in to dil.map</h2>
    
    <p>Hi there!</p>
    
    <p>Click the button below to sign in to dil.map on your Android TV:</p>
    
    <a href="{{MAGIC_LINK_URL}}" class="button">Sign In to Your TV</a>
    
    <p>Or copy and paste this link into your browser:</p>
    <p><code>{{MAGIC_LINK_URL}}</code></p>
    
    <div class="device-info">
      <strong>Device Information:</strong><br>
      Model: {{DEVICE_MODEL}}<br>
      Manufacturer: {{DEVICE_MANUFACTURER}}<br>
      Device ID: {{DEVICE_ID_SHORT}}...
    </div>
    
    <p><small>This link will expire in 15 minutes and can only be used once.</small></p>
    
    <p><small>If you didn't request this, you can safely ignore this email.</small></p>
    
    <hr>
    <p><small>dil.map by Dilworth Creative LLC<br>
    <a href="https://lucindadilworth.com">lucindadilworth.com</a></small></p>
  </div>
</body>
</html>
```

---

## Security Considerations

### 1. Token Generation
- Use cryptographically secure random tokens (e.g., UUID v4)
- Minimum 128 bits of entropy
- Avoid predictable patterns

### 2. Token Storage
- Hash tokens before storing in database
- Use bcrypt or similar one-way hash
- Compare hashed values during verification

### 3. Rate Limiting
- Limit requests per email: 3 per hour
- Limit requests per IP: 10 per hour
- Implement exponential backoff

### 4. Expiration
- Set short expiration times (15 minutes recommended)
- Clean up expired tokens regularly
- Prevent token reuse after expiration

### 5. Device Binding
- Store device ID with token
- Verify device ID on redemption
- Prevent cross-device token usage

### 6. Email Validation
- Validate email format
- Check against disposable email services
- Implement email verification for new accounts

### 7. HTTPS Only
- Enforce HTTPS for all endpoints
- Use TLS 1.2 or higher
- Implement HSTS headers

### 8. Logging
- Log all authentication attempts
- Monitor for suspicious patterns
- Alert on multiple failed attempts

---

## Testing

### Test Request Magic Link
```bash
curl -X POST https://tv.dilly.cloud/api/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "deviceId": "test-device-123",
    "deviceModel": "Test Device",
    "deviceManufacturer": "Test Manufacturer",
    "platform": "android-tv"
  }'
```

### Test Verify Magic Link
```bash
curl "https://tv.dilly.cloud/api/auth/verify?token=YOUR_TOKEN&deviceId=test-device-123"
```

---

## Example Node.js Implementation

See `backend-example/` directory for a complete Express.js implementation with:
- PostgreSQL database
- SendGrid email integration
- JWT session management
- Rate limiting with Redis
- Comprehensive error handling

---

## Support

For implementation questions or issues:
- Email: hello@lucindadilworth.com
- Website: https://lucindadilworth.com
- Instagram: @dil.worth

