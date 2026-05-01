"""
Create database tables
Run this script once to create all tables in the database
"""
import asyncio
from app.db.session import engine
from app.db.base import Base
from app.models.user import User
from app.models.chat import Chat


async def create_tables():
    """Create all database tables"""
    async with engine.begin() as conn:
        # Drop all tables (be careful in production!)
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_tables())
