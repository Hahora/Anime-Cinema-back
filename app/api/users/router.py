from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.api.auth.dependencies import get_current_active_user
from app.api.friends.schemas import UserShort
from app.api.profile.models import User
from app.api.users.schemas import OnlineUsersResponse, CanMessageResponse, UserOnlineResponse
from app.api.users.service import UserService
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/", response_model=List[UserShort])
async def get_all_users_endpoint(
        limit: int = 50,
        offset: int = 0,
        current_user: User = Depends(get_current_active_user),
        user_service: UserService = Depends(get_user_service)
):
    return user_service.get_all_users(limit, offset, current_user.id)


@router.get("/online", response_model=OnlineUsersResponse)
async def get_online_users_endpoint(user_service: UserService = Depends(get_user_service)):
    return user_service.get_online_users_info()


@router.get("/search", response_model=List[UserShort])
async def search_users_endpoint(
        query: str,
        limit: int = 20,
        current_user: User = Depends(get_current_active_user),
        user_service: UserService = Depends(get_user_service)
):
    try:
        users = await user_service.search_users(query, limit, current_user.id)
        return users
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{user_id}/can-message", response_model=CanMessageResponse)
async def check_can_message_endpoint(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        user_service: UserService = Depends(get_user_service)
):
    can_send, reason = await user_service.check_can_message(user_id, current_user.id)
    return CanMessageResponse(can_message=can_send, reason=reason if not can_send else None)


@router.get("/{user_id}/online", response_model=UserOnlineResponse)
async def check_user_online_endpoint(user_id: int, user_service: UserService = Depends(get_user_service)):
    return user_service.check_user_online_status(user_id)
