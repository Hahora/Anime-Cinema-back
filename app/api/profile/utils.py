from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.favorites.models import Favorite
from app.api.watch_progress.models import WatchedAnime


def get_user_stats(db: Session, user_id: int) -> Dict[str, int]:
    stats = db.query(
        func.count(WatchedAnime.id).label('total_anime'),
        func.coalesce(func.sum(WatchedAnime.episodes_watched), 0).label('total_episodes'),
        func.count(Favorite.id).label('favorites_count')
    ).outerjoin(
        Favorite, WatchedAnime.user_id == Favorite.user_id
    ).filter(
        WatchedAnime.user_id == user_id
    ).first()

    total_hours = int(((stats.total_episodes or 0) * 24) // 60)

    return {
        "total_anime": int(stats.total_anime or 0),
        "total_episodes": int(stats.total_episodes or 0),
        "total_hours": total_hours,
        "favorites_count": int(stats.favorites_count or 0)
    }
