from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.profile.models import User
from app.api.watch_progress.schemas import WatchedAnimeItem, WatchedAnimeUpdate, WatchHistoryItem, WatchHistoryAdd
from app.api.watch_progress.service import WatchService
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/watch", tags=["watch"])


def get_watch_service(db: Session = Depends(get_db)) -> WatchService:
    return WatchService(db)


@router.get("/watched", response_model=List[WatchedAnimeItem])
async def get_watched(
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
        watch_service: WatchService = Depends(get_watch_service)
):
    """Список просмотренного"""
    return watch_service.get_watched(current_user.id, limit)


@router.post("/watched", response_model=WatchedAnimeItem)
async def update_watched(
        data: WatchedAnimeUpdate,
        current_user: User = Depends(get_current_active_user),
        watch_service: WatchService = Depends(get_watch_service)
):
    """Обновить прогресс просмотра"""
    return watch_service.update_watched(current_user.id, data)


@router.get("/watched/check/{anime_id}")
async def check_watched(
        anime_id: str,
        current_user: User = Depends(get_current_active_user),
        watch_service: WatchService = Depends(get_watch_service)
):
    """Проверить статус просмотра"""
    return watch_service.check_watched(current_user.id, anime_id)


@router.get("/history", response_model=List[WatchHistoryItem])
async def get_history(
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
        watch_service: WatchService = Depends(get_watch_service)
):
    """История просмотров"""
    return watch_service.get_history(current_user.id, limit)


@router.post("/history", response_model=WatchHistoryItem)
async def add_history(
        data: WatchHistoryAdd,
        current_user: User = Depends(get_current_active_user),
        watch_service: WatchService = Depends(get_watch_service)
):
    """Добавить в историю"""
    return watch_service.add_history(current_user.id, data)
