#!/usr/bin/env python3
"""Quick test script for magic link authentication.

This script tests the magic link endpoints without requiring a real email server.
It uses the database directly to verify the flow.
"""

import asyncio
import sys
from datetime import datetime

import psycopg
from psycopg.rows import dict_row


async def test_magic_link_flow():
    """Test the complete magic link flow."""
    
    # Database URL - adjust if needed
    db_url = "postgresql://postgres:postgres@localhost:5432/tv_api"
    
    print("Testing Magic Link Authentication Flow")
    print("=" * 50)
    
    try:
        # Connect to database
        async with await psycopg.AsyncConnection.connect(
            db_url, row_factory=dict_row
        ) as conn:
            print("✓ Connected to database")
            
            # Check if magic_links table exists
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'magic_links'
                    );
                """)
                result = await cur.fetchone()
                
                if result and result['exists']:
                    print("✓ magic_links table exists")
                else:
                    print("✗ magic_links table does not exist")
                    print("  Run: ./scripts/recreate_database.sh")
                    return False
            
            # Check if users table exists
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    );
                """)
                result = await cur.fetchone()
                
                if result and result['exists']:
                    print("✓ users table exists")
                else:
                    print("✗ users table does not exist")
                    return False
            
            # Test data
            test_email = "test@example.com"
            test_device_id = "test-device-123"
            test_token = "test-token-12345"
            
            print(f"\nTesting with:")
            print(f"  Email: {test_email}")
            print(f"  Device: {test_device_id}")
            
            # Clean up any existing test data
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM magic_links WHERE email = %s",
                    (test_email,)
                )
                await conn.commit()
            
            # Insert a test magic link
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO magic_links 
                        (token, email, device_id, expires_at)
                    VALUES (%s, %s, %s, NOW() + INTERVAL '15 minutes')
                    RETURNING magic_link_id
                """, (test_token, test_email, test_device_id))
                result = await cur.fetchone()
                await conn.commit()
                
                if result:
                    print(f"✓ Created test magic link (ID: {result['magic_link_id']})")
                else:
                    print("✗ Failed to create magic link")
                    return False
            
            # Verify we can retrieve it
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT * FROM magic_links 
                    WHERE token = %s AND device_id = %s
                """, (test_token, test_device_id))
                magic_link = await cur.fetchone()
                
                if magic_link:
                    print("✓ Retrieved magic link from database")
                    print(f"  Expires: {magic_link['expires_at']}")
                    print(f"  Used: {magic_link['used']}")
                else:
                    print("✗ Failed to retrieve magic link")
                    return False
            
            # Test marking as used
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE magic_links
                    SET used = TRUE, used_at = NOW()
                    WHERE token = %s
                """, (test_token,))
                await conn.commit()
                print("✓ Marked magic link as used")
            
            # Verify it was marked as used
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT used, used_at FROM magic_links 
                    WHERE token = %s
                """, (test_token,))
                result = await cur.fetchone()
                
                if result and result['used']:
                    print("✓ Verified magic link is marked as used")
                else:
                    print("✗ Failed to mark magic link as used")
                    return False
            
            # Test user creation
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO users (email)
                    VALUES (%s)
                    ON CONFLICT (email) DO UPDATE 
                    SET email = EXCLUDED.email
                    RETURNING user_id, email
                """, (test_email,))
                user = await cur.fetchone()
                await conn.commit()
                
                if user:
                    print(f"✓ Created/retrieved user (ID: {user['user_id']})")
                else:
                    print("✗ Failed to create user")
                    return False
            
            # Clean up test data
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM magic_links WHERE email = %s",
                    (test_email,)
                )
                await cur.execute(
                    "DELETE FROM users WHERE email = %s",
                    (test_email,)
                )
                await conn.commit()
                print("✓ Cleaned up test data")
            
            print("\n" + "=" * 50)
            print("All database tests passed! ✓")
            print("\nNext steps:")
            print("1. Configure SMTP settings in .env file")
            print("2. Start the server: poetry run uvicorn tv_api.main:app --reload")
            print("3. Test the API at http://localhost:8000/docs")
            return True
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_magic_link_flow())
    sys.exit(0 if success else 1)
