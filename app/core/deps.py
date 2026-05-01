from fastapi import Depends, HTTPException, status, Cookie
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.services.auth_service import get_user_by_id
from app.models.user import User

settings = get_settings()


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not access_token:
        raise credentials_exception
    
    # Extract token from "Bearer <token>" format
    try:
        token = access_token.replace("Bearer ", "")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    return user
