from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import UserRegister, Token

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Allowed email domain
ALLOWED_DOMAIN = "@amzur.com"


def validate_email_domain(email: str) -> bool:
    """Validate that email ends with allowed domain"""
    return email.endswith(ALLOWED_DOMAIN)


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def register_user(db: AsyncSession, user_data: UserRegister) -> User:
    """Register a new user"""
    # Validate email domain
    if not validate_email_domain(user_data.email):
        raise ValueError("Only @amzur.com accounts are allowed")
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise ValueError("Email already registered")
    
    # Create new user
    hashed_pwd = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_pwd,
        auth_provider="email"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user and return user if valid"""
    # Validate email domain
    if not validate_email_domain(email):
        return None
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    # Check if user has a password (not Google OAuth only)
    if not user.password_hash:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_google_user(db: AsyncSession, email: str, google_id: str) -> User:
    """Get or create user from Google OAuth"""
    # Validate email domain
    if not validate_email_domain(email):
        raise ValueError("Only @amzur.com accounts are allowed")
    
    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if user:
        # Update auth_provider if necessary
        if user.auth_provider != "google":
            user.auth_provider = "google"
            await db.commit()
            await db.refresh(user)
        return user
    
    # Create new user
    new_user = User(
        email=email,
        password_hash=None,  # Google OAuth users don't have passwords
        auth_provider="google"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


async def exchange_google_code_for_token(code: str, redirect_uri: str) -> dict:
    """Exchange Google authorization code for access token"""
    token_url = "https://oauth2.googleapis.com/token"
    
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        response.raise_for_status()
        return response.json()


async def get_google_user_info(access_token: str) -> dict:
    """Get user info from Google using access token"""
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(userinfo_url, headers=headers)
        response.raise_for_status()
        return response.json()
