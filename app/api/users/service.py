from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.friends.schemas import UserShort
from app.api.profile.models import User
from app.websocket.websocket_manager import online_users, is_user_online


class UserService:
    def __init__(self, db: Session):
        from app.api.chats.service import ChatService
        self.chat_service = ChatService(db)

        self.db = db

    async def search_users(self, query: str, limit: int, exclude_user_id: int) -> List[UserShort]:
        if not query or len(query) < 2:
            raise ValueError("Запрос должен содержать минимум 2 символа")
        search_pattern = f"%{query.lower()}%"
        return self.db.query(User).filter(
            (func.lower(User.name).like(search_pattern)) | (func.lower(User.username).like(search_pattern)),
            User.id != exclude_user_id
        ).limit(limit).all()

    def get_all_users(self, limit: int, offset: int, exclude_user_id: int) -> List[UserShort]:
        return self.db.query(User).filter(
            User.id != exclude_user_id
        ).order_by(User.id).offset(offset).limit(limit).all()

    def get_online_users_info(self) -> dict:
        return {
            "online_user_ids": list(online_users.keys()),
            "count": len(online_users)
        }

    async def check_can_message(self, user_id: int, current_user_id: int):
        return await self.chat_service.can_send_message_to_user(current_user_id, user_id)

    def check_user_online_status(self, user_id: int) -> dict:
        return {
            "user_id": user_id,
            "is_online": is_user_online(user_id)
        }
