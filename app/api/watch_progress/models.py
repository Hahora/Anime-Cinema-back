from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


class WatchedAnime(Base):
    """
    Таблица просмотренных аниме
    """
    __tablename__ = "watched_anime"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anime_id = Column(String(50), nullable=False, index=True)

    # Прогресс
    episodes_watched = Column(Integer, default=0)
    total_episodes = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)

    # Кеш
    title = Column(String(255))
    poster = Column(String(500))

    last_watched = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watched_anime")

    __table_args__ = (
        UniqueConstraint('user_id', 'anime_id', name='uq_user_anime_watched'),
        Index('idx_watched_user_last', 'user_id', 'last_watched'),
    )


class WatchHistory(Base):
    """
    История просмотров (какие серии смотрел)
    """
    __tablename__ = "watch_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anime_id = Column(String(50), nullable=False, index=True)
    episode_num = Column(Integer, nullable=False)

    # Прогресс в серии (для "продолжить просмотр")
    progress_seconds = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)

    # Кеш
    title = Column(String(255))
    poster = Column(String(500))
    translation_id = Column(String(50))

    watched_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watch_history")

    __table_args__ = (
        Index('idx_history_user_watched', 'user_id', 'watched_at'),
    )
