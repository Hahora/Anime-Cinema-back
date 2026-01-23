from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


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
