from datetime import timedelta
from fastapi import APIRouter, Body, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.models import User, UserCreate, Token, UserInDB
from app.auth.password import verify_password
from app.auth.jwt import (
    create_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, 
    get_current_active_user,
    get_current_admin_user
)
from app.auth.repository import (
    create_user, 
    get_user_by_username, 
    get_all_users,
    delete_user
)

# Create router
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login, get an access token for future requests"""
    user = await get_user_by_username(form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    # Determine scopes based on user role
    scopes = ["user"]
    if user.is_admin:
        scopes.append("admin")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = create_access_token(
        data={"sub": user.username, "scopes": scopes},
        expires_delta=access_token_expires
    )
    
    return token_data


@router.post("/users", response_model=User)
async def register_user(user_create: UserCreate = Body(...)):
    """Register a new user"""
    # Check if user already exists
    existing_user = await get_user_by_username(user_create.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create user
    user = await create_user(user_create)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User creation failed"
        )
    
    # Convert to response model (hide hashed_password)
    return User(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at
    )


@router.get("/users/me", response_model=User)
async def read_users_me(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Get current user information"""
    return User(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at
    )


@router.get("/users", response_model=list[User])
async def read_users(
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Get all users (admin only)"""
    users = await get_all_users()
    return [
        User(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at
        ) 
        for user in users
    ]


@router.get("/validate-token")
async def validate_token(current_user: UserInDB = Depends(get_current_active_user)):
    """Validate the current user's token"""
    return {"valid": True, "username": current_user.username}


@router.delete("/users/{user_id}")
async def delete_user_by_id(
    user_id: str,
    current_user: UserInDB = Depends(get_current_admin_user)
):
    """Delete a user (admin only)"""
    success = await delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {"detail": "User deleted"}
