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

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookie"""
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out"}



@router.get("/google/login")
async def google_login():
    """Return Google OAuth URL"""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend .env."
        )

    redirect_uri = settings.GOOGLE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/auth/google/callback"
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
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        redirect_uri = settings.GOOGLE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/auth/google/callback"
        token_data = await auth_service.exchange_google_code_for_token(code, redirect_uri)
        user_info = await auth_service.get_google_user_info(token_data["access_token"])

        user = await auth_service.get_or_create_google_user(
            db,
            user_info["email"],
            user_info["id"]
        )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )

        redirect_response = RedirectResponse(url=f"{settings.FRONTEND_URL}/chat")
        redirect_response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        return redirect_response

    except ValueError as e:
        error_message = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={error_message}")
    except Exception as e:
        error_message = urllib.parse.quote(f"Authentication failed: {str(e)}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={error_message}")
