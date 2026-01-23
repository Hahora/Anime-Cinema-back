from typing import List

from fastapi import HTTPException, Depends, status, APIRouter, Path
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.favorites.schemas import FavoriteItem, FavoriteAdd
from app.api.favorites.service import FavoriteService
from app.api.profile.models import User
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


def get_favorite_service(db: Session = Depends(get_db)) -> FavoriteService:
    return FavoriteService(db)


async def get_profile_service(db: Session = Depends(get_db)):
    from app.api.profile.service import ProfileService
    return ProfileService(db)


@router.get("/", response_model=List[FavoriteItem])
async def get_favorites(
        limit: int = 50,
        current_user: User = Depends(get_current_active_user),
        favorite_service: FavoriteService = Depends(get_favorite_service)
):
    return favorite_service.get_favorites(current_user.id, limit)


@router.post("/", response_model=FavoriteItem, status_code=status.HTTP_201_CREATED)
async def add_favorite(
        data: FavoriteAdd,
        current_user: User = Depends(get_current_active_user),
        favorite_service: FavoriteService = Depends(get_favorite_service)
):
    try:
        return favorite_service.add_favorite(data, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/check/{anime_id}")
async def check_favorite(
        anime_id: str = Path(..., min_length=1),
        current_user: User = Depends(get_current_active_user),
        favorite_service: FavoriteService = Depends(get_favorite_service)
):
    return {"is_favorite": favorite_service.is_favorite(anime_id, current_user.id)}


@router.delete("/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
        anime_id: str = Path(..., min_length=1),
        current_user: User = Depends(get_current_active_user),
        favorite_service: FavoriteService = Depends(get_favorite_service)
):
    if not favorite_service.remove_favorite(anime_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найден")
