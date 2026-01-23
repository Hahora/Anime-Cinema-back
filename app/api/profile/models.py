from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


class User(Base):
    """
    Таблица пользователей
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)

    avatar_url = Column(String(255), default="/static/images/avatar.webp")
    cover_url = Column(String(255), default="/static/images/cover.webp")
    bio = Column(Text, default="Любитель аниме 🎌")

    message_privacy = Column(String(20), default="all")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    watch_history = relationship("WatchHistory", back_populates="user", cascade="all, delete-orphan")
    watched_anime = relationship("WatchedAnime", back_populates="user", cascade="all, delete-orphan")
