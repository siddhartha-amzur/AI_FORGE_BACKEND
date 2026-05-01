from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # Set to False in production
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency to get DB session
async def get_db():
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
