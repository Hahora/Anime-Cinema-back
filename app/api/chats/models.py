from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


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
    last_read_at = Column(DateTime, nullable=True)

    # ✅ Мягкое удаление
    deleted_at = Column(DateTime, nullable=True)  # Когда удалил чат

    # ✅ Восстановление с чистого листа
    restored_at = Column(DateTime, nullable=True)
    # Все сообщения ДО restored_at будут скрыты

    # Отношения
    chat = relationship("Chat", back_populates="participants")
    user = relationship("User")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    # ✅ Текущее содержимое (может быть отредактировано или "удалено")
    content = Column(Text, nullable=False)

    # ✅ ОРИГИНАЛЬНОЕ содержимое (НИКОГДА не меняется - для суда)
    original_content = Column(Text, nullable=False)  # ← ДОБАВЛЕНО

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ✅ История редактирования
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    edit_history = Column(Text, nullable=True)  # JSON с историей изменений

    # ✅ "Удаление" (на самом деле просто скрытие)
    deleted_at = Column(DateTime, nullable=True)  # ← ДОБАВЛЕНО
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # ← ДОБАВЛЕНО

    # Отношения
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    deleter = relationship("User", foreign_keys=[deleted_by])


class MessageEditHistory(Base):
    __tablename__ = "message_edit_history"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"))
    old_content = Column(Text, nullable=False)
    new_content = Column(Text, nullable=False)
    edited_by = Column(Integer, ForeignKey("users.id"))
    edited_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message")
    editor = relationship("User")
