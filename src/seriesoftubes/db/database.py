"""Database connection and session management"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from seriesoftubes.config import get_config
from seriesoftubes.db.models import Base, User


def get_database_url() -> str:
    """Get database URL from config or environment"""
    # Check environment variable first
    if db_url := os.getenv("DATABASE_URL"):
        # Handle Heroku-style postgres:// URLs
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        # Convert regular postgresql:// to async
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return db_url

    # Fall back to config
    config = get_config()
    db_url = getattr(
        config, "database_url", "sqlite+aiosqlite:///~/.seriesoftubes/db.sqlite"
    )

    # Expand ~ for SQLite URLs
    if db_url.startswith("sqlite"):
        path_part = db_url.split("///")[1]
        if path_part.startswith("~"):
            expanded = Path(path_part).expanduser()
            expanded.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{expanded}"

    return db_url


# Create async engine
db_url = get_database_url()
engine_kwargs = {
    "echo": False,  # Set to True for SQL logging
}

# Only use NullPool for SQLite, use default pool for PostgreSQL
if db_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool
else:
    # For PostgreSQL, use default pool with optimized settings
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Check connection health before using
    })

engine = create_async_engine(db_url, **engine_kwargs)

# Create session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=True,  # Free memory after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    # Ensure system user exists
    await ensure_system_user()


async def ensure_system_user() -> User:
    """Ensure the system user exists"""
    async with async_session() as session:
        # Check if system user exists
        result = await session.execute(select(User).where(User.username == "system"))
        system_user = result.scalar_one_or_none()

        if not system_user:
            # Create system user
            system_user = User(
                username="system",
                is_system=True,
                is_active=True,
                is_admin=True,
            )
            session.add(system_user)
            await session.commit()
            # System user created successfully

        return system_user
