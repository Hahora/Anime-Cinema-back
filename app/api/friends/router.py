from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.friends.schemas import FriendshipResponse, FriendshipCreate
from app.api.friends.service import FriendshipService
from app.api.profile.models import User
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/friends", tags=["friends"])


def get_friendship_service(db: Session = Depends(get_db)) -> FriendshipService:
    return FriendshipService(db)


@router.get("/", response_model=List[FriendshipResponse])
async def get_friends(
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return friendship_service.get_friends(current_user.id)


@router.get("/requests", response_model=List[FriendshipResponse])
async def get_requests(
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return friendship_service.get_friend_requests(current_user.id)


@router.post("/add", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def add_friend(
        data: FriendshipCreate,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return await friendship_service.add_friend(data, current_user)


@router.get("/online")
async def online_friends(
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return friendship_service.get_online_friends(current_user.id)


@router.put("/accept/{friendship_id}", response_model=FriendshipResponse)
async def accept_request(
        friendship_id: int,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return await friendship_service.accept_friend_request(friendship_id, current_user)


@router.put("/reject/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reject_request(
        friendship_id: int,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    friendship_service.reject_friend_request(friendship_id, current_user)


@router.get("/check/{user_id}")
async def check(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return friendship_service.check_friendship(user_id, current_user.id)


@router.get("/status/{user_id}")
async def friend_status(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    return friendship_service.get_friendship_status(user_id, current_user.id)


@router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend_route(
        friendship_id: int,
        current_user: User = Depends(get_current_active_user),
        friendship_service: FriendshipService = Depends(get_friendship_service)
):
    friendship_service.remove_friend(friendship_id, current_user.id)
