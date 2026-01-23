from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.chats.schemas import ChatItem, ChatCreate, MessageItem, MessageCreate
from app.api.chats.service import ChatService
from app.api.profile.models import User
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/chats", tags=["chats"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.get("/", response_model=List[ChatItem])
async def get_chats(
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    return await service.get_chats(current_user.id)


@router.post("/", response_model=ChatItem)
async def create_chat(
        data: ChatCreate,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    return await service.create_chat(data, current_user.id)


@router.put("/{chat_id}/read")
async def mark_chat_read(
        chat_id: int,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    await service.mark_chat_read(chat_id, current_user.id)
    return {"status": "read"}


@router.get("/{chat_id}/messages", response_model=List[MessageItem])
async def get_messages(
        chat_id: int,
        limit: int = 50,
        before_id: Optional[int] = None,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    return await service.get_messages(chat_id, current_user.id, limit, before_id)


@router.post("/{chat_id}/messages", response_model=MessageItem)
async def send_message(
        chat_id: int,
        data: MessageCreate,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    return await service.send_message(chat_id, data, current_user)


@router.put("/{chat_id}/messages/{message_id}", response_model=MessageItem)
async def edit_message(
        chat_id: int,
        message_id: int,
        data: MessageCreate,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    return await service.edit_message(chat_id, message_id, data, current_user.id)


@router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
        chat_id: int,
        message_id: int,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    await service.delete_message(chat_id, message_id, current_user.id)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
        chat_id: int,
        current_user: User = Depends(get_current_active_user),
        service: ChatService = Depends(get_chat_service)
):
    await service.delete_chat(chat_id, current_user.id)
