from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.favorites.schemas import FavoriteItem
from app.api.profile.models import User
from app.api.profile.schemas import UserProfile, UserProfileUpdate, ChangeUsername, ChangePassword
from app.api.profile.service import ProfileService
from app.api.watch_progress.schemas import WatchHistoryItem
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def get_profile_service(db: Session = Depends(get_db)) -> ProfileService:
    return ProfileService(db)


def get_favorite_service(db: Session = Depends(get_db)):
    from app.api.favorites.service import FavoriteService
    return FavoriteService(db)


def get_watch_service(db: Session = Depends(get_db)):
    from app.api.watch_progress.service import WatchService
    return WatchService(db)


@router.get("/me", response_model=UserProfile)
async def get_my_profile(
        current_user: User = Depends(get_current_active_user),
        profile_service: ProfileService = Depends(get_profile_service)
):
    return profile_service.get_my_profile(current_user)


@router.put("/me", response_model=UserProfile)
async def update_profile(
        profile_data: UserProfileUpdate,
        current_user: User = Depends(get_current_active_user),
        profile_service: ProfileService = Depends(get_profile_service)
):
    try:
        return profile_service.update_profile(current_user, profile_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/me/change-username")
async def change_username(
        data: ChangeUsername,
        current_user: User = Depends(get_current_active_user),
        profile_service: ProfileService = Depends(get_profile_service)
):
    try:
        return profile_service.change_username(current_user, data)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.patch("/me/change-password")
async def change_password(
        data: ChangePassword,
        current_user: User = Depends(get_current_active_user),
        profile_service: ProfileService = Depends(get_profile_service)
):
    try:
        return profile_service.change_password(current_user, data)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/{user_id}/history", response_model=List[WatchHistoryItem])
async def get_user_history(
        user_id: int,
        limit: int = 50,
        watch_service=Depends(get_watch_service)
):
    return watch_service.get_user_history(user_id, limit)


@router.get("/{user_id}/favorites", response_model=List[FavoriteItem])
async def get_user_favorites(
        user_id: int,
        limit: int = 50,
        favorite_service=Depends(get_favorite_service),
        profile_service=Depends(get_profile_service)
):
    if not profile_service.exists(user_id):
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return favorite_service.get_user_favorites(user_id, limit)


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
        user_id: int,
        profile_service: ProfileService = Depends(get_profile_service)
):
    try:
        return profile_service.get_public_profile(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
