import os
import uuid
from datetime import datetime
from typing import Dict, Optional, List, Any
import pymysql
import pymysql.cursors
import asyncio
from pydantic import EmailStr

from app.auth.models import UserInDB, UserCreate, UserUpdate
from app.auth.password import get_password_hash
from app.utils.env import get_db_config


# Get database configuration from environment variables
DB_CONFIG = get_db_config()


def get_connection():
    """Get database connection"""
    return pymysql.connect(**DB_CONFIG)


async def setup_db():
    """Create tables if they don't exist"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Create tokens table to store active tokens
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')

        conn.commit()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error setting up database: {e}")
    finally:
        conn.close()


async def create_user(user_create: UserCreate) -> Optional[UserInDB]:
    """Create a new user"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if username or email already exists
            cursor.execute(
                "SELECT * FROM users WHERE username = %s OR email = %s",
                (user_create.username, user_create.email)
            )
            existing_user = cursor.fetchone()
            if existing_user:
                print(f"User already exists with username {user_create.username} or email {user_create.email}")
                return None

            # Generate user ID and hash password
            user_id = str(uuid.uuid4())
            hashed_password = get_password_hash(user_create.password)
            created_at = datetime.now()

            # Insert user into database
            cursor.execute(
                "INSERT INTO users (id, username, email, hashed_password, is_active, is_admin) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    user_id,
                    user_create.username,
                    user_create.email,
                    hashed_password,
                    user_create.is_active,
                    user_create.is_admin
                )
            )
            conn.commit()

            # Return the created user
            user_in_db = UserInDB(
                id=user_id,
                username=user_create.username,
                email=user_create.email,
                hashed_password=hashed_password,
                is_active=user_create.is_active,
                is_admin=user_create.is_admin,
                created_at=created_at
            )
            print(f"Created user: {user_in_db.username}")
            return user_in_db
    except Exception as e:
        conn.rollback()
        print(f"Error creating user: {e}")
        return None
    finally:
        conn.close()


async def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Get user by ID"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                # Convert boolean values (MySQL returns 1/0 for boolean fields)
                user_data['is_active'] = bool(user_data['is_active'])
                user_data['is_admin'] = bool(user_data['is_admin'])
                return UserInDB(**user_data)
            return None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None
    finally:
        conn.close()


async def get_user_by_username(username: str) -> Optional[UserInDB]:
    """Get user by username"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            if user_data:
                # Convert boolean values
                user_data['is_active'] = bool(user_data['is_active'])
                user_data['is_admin'] = bool(user_data['is_admin'])
                return UserInDB(**user_data)
            return None
    except Exception as e:
        print(f"Error getting user by username: {e}")
        return None
    finally:
        conn.close()


async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cursor.fetchone()
            if user_data:
                # Convert boolean values
                user_data['is_active'] = bool(user_data['is_active'])
                user_data['is_admin'] = bool(user_data['is_admin'])
                return UserInDB(**user_data)
            return None
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None
    finally:
        conn.close()


async def get_all_users() -> List[UserInDB]:
    """Get all users"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            users_data = cursor.fetchall()
            users = []
            for user_data in users_data:
                # Convert boolean values
                user_data['is_active'] = bool(user_data['is_active'])
                user_data['is_admin'] = bool(user_data['is_admin'])
                users.append(UserInDB(**user_data))
            return users
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []
    finally:
        conn.close()


async def update_user(user_id: str, update_data: UserUpdate) -> Optional[UserInDB]:
    """Update user information"""
    conn = get_connection()
    try:
        # First get the current user data
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            current_user = cursor.fetchone()
            if not current_user:
                return None

            # Build update query dynamically based on provided fields
            update_fields = []
            update_values = []

            if update_data.username is not None:
                update_fields.append("username = %s")
                update_values.append(update_data.username)

            if update_data.email is not None:
                update_fields.append("email = %s")
                update_values.append(update_data.email)

            if update_data.password is not None:
                update_fields.append("hashed_password = %s")
                update_values.append(get_password_hash(update_data.password))

            if update_data.is_active is not None:
                update_fields.append("is_active = %s")
                update_values.append(update_data.is_active)

            if update_data.is_admin is not None:
                update_fields.append("is_admin = %s")
                update_values.append(update_data.is_admin)

            # If there are no fields to update, return current user
            if not update_fields:
                # Convert boolean values
                current_user['is_active'] = bool(current_user['is_active'])
                current_user['is_admin'] = bool(current_user['is_admin'])
                return UserInDB(**current_user)

            # Build and execute update query
            update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            update_values.append(user_id)

            cursor.execute(update_query, update_values)
            conn.commit()

            # Return updated user
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            updated_user = cursor.fetchone()
            if updated_user:
                # Convert boolean values
                updated_user['is_active'] = bool(updated_user['is_active'])
                updated_user['is_admin'] = bool(updated_user['is_admin'])
                return UserInDB(**updated_user)

            return None
    except Exception as e:
        conn.rollback()
        print(f"Error updating user: {e}")
        return None
    finally:
        conn.close()


async def delete_user(user_id: str) -> bool:
    """Delete user"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"Error deleting user: {e}")
        return False
    finally:
        conn.close()


async def store_active_token(user_id: str, token: str, expires_at: datetime) -> bool:
    """Store active token for a user"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Delete any existing tokens for this user
            cursor.execute("DELETE FROM tokens WHERE user_id = %s", (user_id,))

            # Insert new token
            token_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO tokens (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
                (token_id, user_id, token, expires_at)
            )
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error storing token: {e}")
        return False
    finally:
        conn.close()


async def get_active_token(user_id: str) -> Optional[Dict[str, Any]]:
    """Get active token for a user"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tokens WHERE user_id = %s AND expires_at > NOW()",
                (user_id,)
            )
            token_data = cursor.fetchone()
            return token_data
    except Exception as e:
        print(f"Error getting active token: {e}")
        return None
    finally:
        conn.close()


async def validate_token(token: str) -> Optional[str]:
    """Validate token and return user_id if valid"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM tokens WHERE token = %s AND expires_at > NOW()",
                (token,)
            )
            result = cursor.fetchone()
            if result:
                return result['user_id']
            return None
    except Exception as e:
        print(f"Error validating token: {e}")
        return None
    finally:
        conn.close()


async def invalidate_user_tokens(user_id: str) -> bool:
    """Invalidate all tokens for a user"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tokens WHERE user_id = %s", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error invalidating tokens: {e}")
        return False
    finally:
        conn.close()


async def clean_expired_tokens() -> int:
    """Clean expired tokens and return number of deleted tokens"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tokens WHERE expires_at <= NOW()")
            conn.commit()
            return cursor.rowcount
    except Exception as e:
        conn.rollback()
        print(f"Error cleaning expired tokens: {e}")
        return 0
    finally:
        conn.close()


async def create_initial_admin() -> None:
    """Create admin user if no users exist"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if any users exist
            cursor.execute("SELECT COUNT(*) as count FROM users")
            result = cursor.fetchone()

            if result and result['count'] == 0:
                print("No users found, creating admin user")
                admin_user = UserCreate(
                    username="admin",
                    email="admin@example.com",
                    password="adminpassword",
                    is_active=True,
                    is_admin=True
                )
                await create_user(admin_user)
    except Exception as e:
        print(f"Error creating initial admin: {e}")
    finally:
        conn.close()
