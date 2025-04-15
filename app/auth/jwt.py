from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import ValidationError
from typing import Optional, List, Dict
import time

from app.auth.models import TokenData, UserInDB
from app.auth.mysql_repository import get_user_by_username, store_active_token, validate_token, invalidate_user_tokens as db_invalidate_user_tokens
from app.utils.env import get_jwt_settings

# Get JWT settings from environment variables
jwt_settings = get_jwt_settings()
SECRET_KEY = jwt_settings['secret_key']
ALGORITHM = jwt_settings['algorithm']
ACCESS_TOKEN_EXPIRE_MINUTES = jwt_settings['access_token_expire_minutes']

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    scopes={
        "user": "Access user information",
        "admin": "Admin privileges"
    },
)

async def invalidate_user_tokens(username: str):
    """Invalidate all tokens for a specific user"""
    if username:
        print(f"[TOKEN] Invalidating previous tokens for user {username}")
        user = await get_user_by_username(username)
        if user:
            await db_invalidate_user_tokens(user.id)

async def is_token_valid(token: str, username: str) -> bool:
    """Check if token is the active token for the user"""
    try:
        # Verify token hasn't expired
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expiration = payload.get("exp", 0)
        current_time = int(time.time())

        if current_time >= expiration:
            print(f"[TOKEN] Token expired for user {username}, exp: {expiration}, now: {current_time}")
            return False

        # Verify token is still valid in MySQL
        user = await get_user_by_username(username)
        if not user:
            print(f"[TOKEN] User not found: {username}")
            return False

        user_id_from_token = await validate_token(token)
        if not user_id_from_token or user_id_from_token != user.id:
            print(f"[TOKEN] Token not valid for user {username}")
            return False

        return True
    except Exception as e:
        print(f"[TOKEN] Error validating token: {e}")
        return False

async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    username = to_encode.get("sub")

    # Use current time from time.time() - more reliable than datetime.utcnow()
    current_time = int(time.time())

    if expires_delta:
        expire_time = current_time + int(expires_delta.total_seconds())
    else:
        expire_time = current_time + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    # Debug logging
    print(f"[TOKEN DEBUG] Creating token - current time: {current_time}, expires at: {expire_time}, difference: {expire_time - current_time} seconds")

    # Make sure expiration is at least 10 minutes in the future
    if expire_time <= current_time + 600:
        print(f"[TOKEN ERROR] Expiration timestamp is too close to current time! Setting to 30 minutes from now.")
        expire_time = current_time + 1800  # 30 minutes

    to_encode.update({"exp": expire_time})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Store token in MySQL
    if username:
        user = await get_user_by_username(username)
        if user:
            # Store token in MySQL with expiration
            expires_datetime = datetime.fromtimestamp(expire_time)
            await store_active_token(user.id, encoded_jwt, expires_datetime)
            print(f"[TOKEN] Created new active token for user {username}, expires at {expires_datetime.isoformat()}")

    return {
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "expires_at": expire_time
    }

async def get_user_from_token(token: str) -> Optional[UserInDB]:
    """Get user from token without using dependencies"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            return None

        # Get user from database
        user = await get_user_by_username(username)
        if not user or not user.is_active:
            return None

        # Check if token is still valid in MySQL
        user_id_from_token = await validate_token(token)
        if not user_id_from_token or user_id_from_token != user.id:
            return None

        return user
    except Exception as e:
        print(f"[TOKEN] Error getting user from token: {e}")
        return None

async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme)
) -> UserInDB:
    """Validate token and get current user"""
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Check if token has expired
        expiration = payload.get("exp", 0)
        current_time = int(time.time())
        if current_time >= expiration:
            print(f"[TOKEN] Token expired for user {username}, exp: {expiration}, now: {current_time}")
            raise credentials_exception

        # Check if token is still valid in MySQL
        user = await get_user_by_username(username)
        if not user:
            print(f"[TOKEN] User not found: {username}")
            raise credentials_exception

        user_id_from_token = await validate_token(token)
        if not user_id_from_token or user_id_from_token != user.id:
            print(f"[TOKEN] Token not valid for user {username}")
            raise credentials_exception

        token_scopes = payload.get("scopes", [])
        token_data = TokenData(sub=username, scopes=token_scopes)

    except (JWTError, ValidationError) as e:
        print(f"[TOKEN] JWT validation error: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"[TOKEN] Unexpected error: {e}")
        raise credentials_exception

    # Get user from database
    user = await get_user_by_username(token_data.sub)
    if user is None:
        raise credentials_exception

    # Check scopes
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required scope: {scope}",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user

async def get_current_active_user(
    current_user: UserInDB = Security(get_current_user, scopes=["user"])
) -> UserInDB:
    """Check if user is active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_admin_user(
    current_user: UserInDB = Security(get_current_user, scopes=["admin"])
) -> UserInDB:
    """Check if user is admin"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
