from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.favorites.models import Favorite
from app.api.favorites.schemas import FavoriteItem, FavoriteAdd


class FavoriteService:
    def __init__(self, db: Session):
        self.db = db

    def get_favorites(self, user_id: int, limit: int = 50) -> List[FavoriteItem]:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id)
            .order_by(desc(Favorite.added_at))
            .limit(limit)
            .all()
        )

    def add_favorite(self, data: FavoriteAdd, user_id: int) -> FavoriteItem:
        if self.db.query(Favorite).filter(Favorite.user_id == user_id, Favorite.anime_id == data.anime_id).first():
            raise ValueError("Already in favorites")
        new_fav = Favorite(user_id=user_id, **data.dict())
        self.db.add(new_fav)
        self.db.commit()
        self.db.refresh(new_fav)
        return new_fav

    def remove_favorite(self, anime_id: str, user_id: int) -> bool:
        deleted = (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id, Favorite.anime_id == anime_id)
            .delete()
        )
        if deleted:
            self.db.commit()
        return bool(deleted)

    def is_favorite(self, anime_id: str, user_id: int) -> bool:
        return (
                self.db.query(Favorite)
                .filter(Favorite.user_id == user_id, Favorite.anime_id == anime_id)
                .first()
                is not None
        )

    def get_user_favorites(self, user_id: int, limit: int = 50) -> List[FavoriteItem]:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id)
            .order_by(desc(Favorite.added_at))
            .limit(limit)
            .all()
        )
