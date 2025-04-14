from datetime import datetime, timedelta
import secrets
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import ValidationError
from typing import Optional, List, Dict
import time

from app.auth.models import TokenData, UserInDB
from app.auth.repository import get_user_by_username

# Security settings
SECRET_KEY = secrets.token_hex(32)  # Generate secure random key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Token management
active_tokens: Dict[str, str] = {}  # username -> token

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    scopes={
        "user": "Access user information",
        "admin": "Admin privileges"
    },
)


def invalidate_user_tokens(username: str):
    """Invalidate all tokens for a specific user"""
    if username in active_tokens:
        print(f"[TOKEN] Invalidating previous tokens for user {username}")
        active_tokens.pop(username, None)


def is_token_valid(token: str, username: str) -> bool:
    """Check if token is the active token for the user"""
    if username not in active_tokens:
        print(f"[TOKEN] No active token found for user {username}")
        return False
    
    if active_tokens[username] != token:
        print(f"[TOKEN] Token mismatch for user {username}")
        return False
    
    try:
        # Also verify token hasn't expired
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expiration = payload.get("exp", 0)
        current_time = int(time.time())
        
        if current_time >= expiration:
            print(f"[TOKEN] Token expired for user {username}, exp: {expiration}, now: {current_time}")
            active_tokens.pop(username, None)
            return False
        
        return True
    except JWTError:
        print(f"[TOKEN] Invalid token format for user {username}")
        active_tokens.pop(username, None)
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
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
    
    # Store as active token for this user (invalidating any previous tokens)
    if username:
        invalidate_user_tokens(username)
        active_tokens[username] = encoded_jwt
        print(f"[TOKEN] Created new active token for user {username}, expires at {datetime.fromtimestamp(expire_time).isoformat()}")
    
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
            
        # Check if token is still valid in our active_tokens map
        if not is_token_valid(token, username):
            return None
            
        # Get user from database
        user = await get_user_by_username(username)
        if not user or not user.is_active:
            return None
            
        return user
    except Exception:
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
        
        # Verify token is still valid in our active_tokens map
        if not is_token_valid(token, username):
            print(f"[AUTH] Token invalid for user {username}")
            raise credentials_exception
        
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(sub=username, scopes=token_scopes)
    
    except (JWTError, ValidationError):
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
