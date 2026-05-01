"""
Add auth_provider column to users table
Run this once to migrate existing users table
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine


async def migrate_users_table():
    """Add auth_provider column to users table"""
    async with engine.begin() as conn:
        # Add auth_provider column with default value 'email'
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR NOT NULL DEFAULT 'email'"
        ))
        
        # Make password_hash nullable
        await conn.execute(text(
            "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"
        ))
    
    print("✅ Users table migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate_users_table())
