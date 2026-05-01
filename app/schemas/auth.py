from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID


class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response"""
    id: UUID
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token"""
    access_token: str
    token_type: str = "bearer"
