from fastapi import Depends, HTTPException, status, Cookie, Header
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
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_source = access_token
    if not token_source and authorization:
        token_source = authorization

    if not token_source:
        raise credentials_exception
    
    # Extract token from "Bearer <token>" format
    try:
        token_source = token_source.strip().strip('"')
        token = token_source.replace("Bearer ", "") if token_source.startswith("Bearer ") else token_source
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
