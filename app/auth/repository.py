import os
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Optional, List
import json

from app.auth.models import UserInDB, UserCreate
from app.auth.password import get_password_hash

# Database setup
DB_PATH = "auth.db"


def dict_factory(cursor, row):
    """Convert SQLite row to dict"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def setup_db():
    """Create database and tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()


def get_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


async def create_user(user_create: UserCreate) -> UserInDB:
    """Create a new user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if username or email already exists
        cursor.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (user_create.username, user_create.email)
        )
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return None
        
        # Generate user ID and hash password
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user_create.password)
        created_at = datetime.now().isoformat()
        
        # Insert user into database
        cursor.execute(
            "INSERT INTO users (id, username, email, hashed_password, is_active, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                user_create.username,
                user_create.email,
                hashed_password,
                1 if user_create.is_active else 0,
                1 if user_create.is_admin else 0,
                created_at
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
            created_at=datetime.fromisoformat(created_at)
        )
        return user_in_db
    except Exception as e:
        print(f"Error creating user: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


async def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Get user by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return None
    
    return UserInDB(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=user_data["hashed_password"],
        is_active=bool(user_data["is_active"]),
        is_admin=bool(user_data["is_admin"]),
        created_at=datetime.fromisoformat(user_data["created_at"])
    )


async def get_user_by_username(username: str) -> Optional[UserInDB]:
    """Get user by username"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return None
    
    return UserInDB(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=user_data["hashed_password"],
        is_active=bool(user_data["is_active"]),
        is_admin=bool(user_data["is_admin"]),
        created_at=datetime.fromisoformat(user_data["created_at"])
    )


async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user by email"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return None
    
    return UserInDB(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=user_data["hashed_password"],
        is_active=bool(user_data["is_active"]),
        is_admin=bool(user_data["is_admin"]),
        created_at=datetime.fromisoformat(user_data["created_at"])
    )


async def get_all_users() -> List[UserInDB]:
    """Get all users"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users")
    users_data = cursor.fetchall()
    conn.close()
    
    return [
        UserInDB(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            hashed_password=user_data["hashed_password"],
            is_active=bool(user_data["is_active"]),
            is_admin=bool(user_data["is_admin"]),
            created_at=datetime.fromisoformat(user_data["created_at"])
        )
        for user_data in users_data
    ]


async def update_user(user_id: str, update_data: dict) -> Optional[UserInDB]:
    """Update user information"""
    user = await get_user_by_id(user_id)
    if not user:
        return None
    
    conn = get_connection()
    cursor = conn.cursor()
    
    update_fields = []
    update_values = []
    
    if "username" in update_data and update_data["username"]:
        update_fields.append("username = ?")
        update_values.append(update_data["username"])
    
    if "email" in update_data and update_data["email"]:
        update_fields.append("email = ?")
        update_values.append(update_data["email"])
    
    if "password" in update_data and update_data["password"]:
        update_fields.append("hashed_password = ?")
        update_values.append(get_password_hash(update_data["password"]))
    
    if "is_active" in update_data:
        update_fields.append("is_active = ?")
        update_values.append(1 if update_data["is_active"] else 0)
    
    if "is_admin" in update_data:
        update_fields.append("is_admin = ?")
        update_values.append(1 if update_data["is_admin"] else 0)
    
    if not update_fields:
        conn.close()
        return user
    
    try:
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(user_id)
        
        cursor.execute(query, update_values)
        conn.commit()
        
        return await get_user_by_id(user_id)
    except Exception as e:
        print(f"Error updating user: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


async def delete_user(user_id: str) -> bool:
    """Delete user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except:
        conn.rollback()
        return False
    finally:
        conn.close()


# Create an admin user on startup if no users exist
async def create_initial_admin():
    setup_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    result = cursor.fetchone()
    conn.close()
    
    if result["count"] == 0:
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com",
            password="adminpassword",  # Change this in production!
            is_active=True,
            is_admin=True
        )
        await create_user(admin_user)
