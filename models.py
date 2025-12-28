from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import datetime 


class User(Base):
    """
    Таблица пользователей
    """
    __tablename__ = "users"

    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Профиль
    avatar_url = Column(String(500), default="https://i.pravatar.cc/300")
    cover_url = Column(String(500), default="https://images.unsplash.com/photo-1578632767115-351597cf2477?w=1200")
    bio = Column(Text, default="Любитель аниме 🎌")
    
    # Служебные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи (один пользователь → много записей)
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    watch_history = relationship("WatchHistory", back_populates="user", cascade="all, delete-orphan")
    watched_anime = relationship("WatchedAnime", back_populates="user", cascade="all, delete-orphan")


class Favorite(Base):
    """
    Таблица избранного
    """
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anime_id = Column(String(50), nullable=False, index=True)
    
    # Кешируем данные, чтобы не запрашивать каждый раз
    title = Column(String(255))
    poster = Column(String(500))
    year = Column(Integer)
    rating = Column(Float)
    
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с пользователем
    user = relationship("User", back_populates="favorites")

    # Один пользователь не может добавить одно аниме дважды
    __table_args__ = (
        UniqueConstraint('user_id', 'anime_id', name='uq_user_anime_favorite'),
        Index('idx_favorites_user_added', 'user_id', 'added_at'),
    )


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

class Friendship(Base):
    __tablename__ = "friendships"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Отношения
    user = relationship("User", foreign_keys=[user_id], backref="sent_requests")
    friend = relationship("User", foreign_keys=[friend_id], backref="received_requests")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),
    )    

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # friend_request, friend_accepted, friend_rejected
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sender_name = Column(String)
    sender_avatar = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", foreign_keys=[user_id], backref="notifications")
    sender = relationship("User", foreign_keys=[sender_id])
    
    __table_args__ = (
        Index('ix_notifications_user_id', 'user_id'),
        Index('ix_notifications_is_read', 'is_read'),
        Index('ix_notifications_created_at', 'created_at'),
    )

# ═══════════════════════════════════════════
# ЧАТЫ И СООБЩЕНИЯ
# ═══════════════════════════════════════════

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, default="private")  # private, group (на будущее)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    participants = relationship("ChatParticipant", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)  # Для непрочитанных
    
    # Отношения
    chat = relationship("Chat", back_populates="participants")
    user = relationship("User")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    
    # Отношения
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User")