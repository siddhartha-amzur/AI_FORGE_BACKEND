from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import urllib.parse

from app.db.session import get_db
from app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from app.services import auth_service
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    try:
        user = await auth_service.register_user(db, user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login user and return JWT token"""
    user = await auth_service.authenticate_user(db, user_data.email, user_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/google/login")
async def google_login():
    """Redirect to Google OAuth login"""
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline"
    )
    return {"url": google_auth_url}


@router.get("/google/callback")
async def google_callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for token
        redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
        token_data = await auth_service.exchange_google_code_for_token(code, redirect_uri)
        
        # Get user info
        user_info = await auth_service.get_google_user_info(token_data["access_token"])
        
        # Get or create user
        user = await auth_service.get_or_create_google_user(
            db, 
            user_info["email"],
            user_info["id"]
        )
        
        # Create JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        # Set httpOnly cookie
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        # Redirect to frontend with success
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/chat")
        
    except ValueError as e:
        # Domain validation failed
        print(f"Domain validation error: {e}")
        error_message = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={error_message}")
    except Exception as e:
        # Other errors
        print(f"OAuth error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        error_message = urllib.parse.quote(f"Authentication failed: {str(e)}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={error_message}")

