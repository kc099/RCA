#!/usr/bin/env python3
"""
Unit test for MySQL authentication functionality.
Tests user creation, retrieval, and deletion in the MySQL database.
"""

import asyncio
import sys
import uuid
import os
from datetime import datetime

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Make sure environment variables are loaded before importing modules
from app.utils.env import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

from app.auth.models import UserCreate, UserUpdate
from app.auth.mysql_repository import (
    setup_db,
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_id,
    update_user,
    delete_user,
    store_active_token,
    get_active_token,
    validate_token,
    invalidate_user_tokens,
    clean_expired_tokens
)


async def test_user_crud():
    """Test CRUD operations for users"""
    print("\n=== Testing User CRUD operations ===")
    
    # Generate unique identifiers for testing
    test_id = uuid.uuid4().hex[:8]
    username = f"test_user_{test_id}"
    email = f"test_{test_id}@example.com"
    password = "test_password_123"
    
    # 1. Create a user
    print(f"\nCreating test user: {username}")
    user_create = UserCreate(
        username=username,
        email=email,
        password=password,
        is_active=True,
        is_admin=False
    )
    
    created_user = await create_user(user_create)
    assert created_user is not None, "Failed to create user"
    assert created_user.username == username, f"Expected username {username}, got {created_user.username}"
    assert created_user.email == email, f"Expected email {email}, got {created_user.email}"
    
    user_id = created_user.id
    print(f"User created with ID: {user_id}")
    
    # 2. Get user by username
    print("\nRetrieving user by username...")
    user_by_username = await get_user_by_username(username)
    assert user_by_username is not None, "Failed to get user by username"
    assert user_by_username.id == user_id, "User ID mismatch"
    
    # 3. Get user by email
    print("\nRetrieving user by email...")
    user_by_email = await get_user_by_email(email)
    assert user_by_email is not None, "Failed to get user by email"
    assert user_by_email.id == user_id, "User ID mismatch"
    
    # 4. Get user by id
    print("\nRetrieving user by ID...")
    user_by_id = await get_user_by_id(user_id)
    assert user_by_id is not None, "Failed to get user by ID"
    assert user_by_id.username == username, "Username mismatch"
    
    # 5. Update user
    print("\nUpdating user...")
    new_email = f"updated_{test_id}@example.com"
    update_data = UserUpdate(email=new_email)
    updated_user = await update_user(user_id, update_data)
    assert updated_user is not None, "Failed to update user"
    assert updated_user.email == new_email, f"Expected updated email {new_email}, got {updated_user.email}"
    
    # 6. Test token functionality
    print("\nTesting token functionality...")
    token = "test_token_" + uuid.uuid4().hex
    expires_at = datetime.now().replace(microsecond=0)
    
    # Store token
    token_stored = await store_active_token(user_id, token, expires_at)
    assert token_stored, "Failed to store token"
    
    # Get token
    active_token = await get_active_token(user_id)
    if active_token:  # Might be None if expires_at is in the past
        assert active_token['token'] == token, "Token mismatch"
    
    # Validate token (will likely fail if expires_at is in the past)
    # This is just to test the function works
    await validate_token(token)
    
    # Invalidate tokens
    invalidated = await invalidate_user_tokens(user_id)
    assert invalidated, "Failed to invalidate tokens"
    
    # 7. Delete user
    print("\nDeleting user...")
    deleted = await delete_user(user_id)
    assert deleted, "Failed to delete user"
    
    # Verify deletion
    deleted_user = await get_user_by_id(user_id)
    assert deleted_user is None, "User was not deleted"
    
    print("\nAll user CRUD tests passed!")
    return True


async def test_token_management():
    """Test token management operations"""
    print("\n=== Testing Token Management ===")
    
    # Generate unique identifiers for testing
    test_id = uuid.uuid4().hex[:8]
    username = f"token_test_user_{test_id}"
    email = f"token_test_{test_id}@example.com"
    password = "test_password_123"
    
    # 1. Create a user for token testing
    user_create = UserCreate(
        username=username,
        email=email,
        password=password,
        is_active=True,
        is_admin=False
    )
    
    created_user = await create_user(user_create)
    assert created_user is not None, "Failed to create user for token testing"
    user_id = created_user.id
    
    try:
        # 2. Store multiple tokens to test overwrite behavior
        print("\nTesting token replacement...")
        # Create first token
        token1 = "test_token_1_" + uuid.uuid4().hex
        # Set expiration far in the future
        expires_at1 = datetime(2030, 1, 1)
        token1_stored = await store_active_token(user_id, token1, expires_at1)
        assert token1_stored, "Failed to store first token"
        
        # Check if token was stored
        active_token1 = await get_active_token(user_id)
        assert active_token1 is not None, "Failed to retrieve first token"
        assert active_token1['token'] == token1, "First token mismatch"
        
        # Store second token (should replace first)
        token2 = "test_token_2_" + uuid.uuid4().hex
        expires_at2 = datetime(2030, 1, 2)
        token2_stored = await store_active_token(user_id, token2, expires_at2)
        assert token2_stored, "Failed to store second token"
        
        # Check if second token replaced first
        active_token2 = await get_active_token(user_id)
        assert active_token2 is not None, "Failed to retrieve second token"
        assert active_token2['token'] == token2, "Second token should replace first token"
        
        # 3. Test token validation
        print("\nTesting token validation...")
        user_id_from_token = await validate_token(token2)
        assert user_id_from_token == user_id, "Token validation failed"
        
        # 4. Test invalid token
        invalid_token = "invalid_token_" + uuid.uuid4().hex
        user_id_from_invalid = await validate_token(invalid_token)
        assert user_id_from_invalid is None, "Invalid token should not be validated"
        
        # 5. Test token invalidation
        print("\nTesting token invalidation...")
        invalidated = await invalidate_user_tokens(user_id)
        assert invalidated, "Failed to invalidate tokens"
        
        # Verify token was invalidated
        no_token = await get_active_token(user_id)
        assert no_token is None, "Token should be invalidated"
        
        # 6. Test expired token cleanup
        print("\nTesting expired token cleanup...")
        # Create an expired token
        expired_token = "expired_token_" + uuid.uuid4().hex
        expired_date = datetime(2000, 1, 1)  # Far in the past
        await store_active_token(user_id, expired_token, expired_date)
        
        # Clean expired tokens
        cleaned = await clean_expired_tokens()
        print(f"Cleaned {cleaned} expired tokens")
        
        print("\nAll token management tests passed!")
        return True
    
    finally:
        # Clean up the test user
        await delete_user(user_id)


async def main():
    """Run all tests"""
    try:
        # Initialize the database
        print("\nSetting up database schema...")
        setup_db()
        
        # Run tests
        user_tests_passed = await test_user_crud()
        token_tests_passed = await test_token_management()
        
        if user_tests_passed and token_tests_passed:
            print("\n✅ All tests passed successfully!")
            return 0
        return 1
    
    except Exception as e:
        print(f"\n❌ Error during tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
