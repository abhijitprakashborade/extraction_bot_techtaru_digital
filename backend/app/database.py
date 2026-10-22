"""
Async SQLite Database — SQLAlchemy 2.x style
Stores extraction history so users can review past results.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, Text, DateTime
from datetime import datetime, timezone
from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ExtractionRecord(Base):
    """Persisted extraction history."""
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(50))
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_text_length: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str] = mapped_column(Text)         # Full JSON result
    warnings: Mapped[str] = mapped_column(Text, default="[]")
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


async def init_db():
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a session per request."""
    async with AsyncSessionFactory() as session:
        yield session
