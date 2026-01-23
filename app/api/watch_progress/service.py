from typing import List

from fastapi import HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.api.watch_progress.models import WatchedAnime, WatchHistory
from app.api.watch_progress.schemas import WatchedAnimeItem, WatchedAnimeUpdate, WatchHistoryItem, WatchHistoryAdd


class WatchService:
    def __init__(self, db: Session):
        self.db = db

    def get_watched(self, user_id: int, limit: int = 50) -> List[WatchedAnimeItem]:
        return self.db.query(WatchedAnime).filter(
            WatchedAnime.user_id == user_id
        ).order_by(desc(WatchedAnime.last_watched)).limit(limit).all()

    def update_watched(self, user_id: int, data: WatchedAnimeUpdate) -> WatchedAnimeItem:
        watched = self.db.query(WatchedAnime).filter(
            WatchedAnime.user_id == user_id,
            WatchedAnime.anime_id == data.anime_id
        ).first()
        if watched:
            for key, value in data.dict(exclude={'anime_id'}).items():
                setattr(watched, key, value)
            watched.last_watched = func.now()
        else:
            watched = WatchedAnime(user_id=user_id, **data.dict())
            self.db.add(watched)
        self.db.commit()
        self.db.refresh(watched)
        return watched

    def check_watched(self, user_id: int, anime_id: str) -> dict:
        watched = self.db.query(WatchedAnime).filter(
            WatchedAnime.user_id == user_id,
            WatchedAnime.anime_id == anime_id
        ).first()
        if not watched:
            return {"is_watched": False, "episodes_watched": 0, "is_completed": False}
        return {
            "is_watched": True,
            "episodes_watched": watched.episodes_watched,
            "total_episodes": watched.total_episodes,
            "is_completed": watched.is_completed
        }

    def get_history(self, user_id: int, limit: int = 50) -> List[WatchHistoryItem]:
        return self.db.query(WatchHistory).filter(
            WatchHistory.user_id == user_id
        ).order_by(desc(WatchHistory.watched_at)).limit(limit).all()

    def add_history(self, user_id: int, data: WatchHistoryAdd) -> WatchHistoryItem:
        history = self.db.query(WatchHistory).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.anime_id == data.anime_id,
            WatchHistory.episode_num == data.episode_num
        ).first()
        if history:
            history.watched_at = func.now()
            history.progress_seconds = data.progress_seconds
            history.duration_seconds = data.duration_seconds
        else:
            history = WatchHistory(user_id=user_id, **data.dict())
            self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_user_history(self, user_id: int, limit: int = 50) -> List[WatchHistoryItem]:
        from app.api.profile.models import User
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        return self.get_history(user_id, limit)
