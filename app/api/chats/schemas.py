from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="Текст сообщения")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Сообщение не может быть пустым')
        return v


class ChatCreate(BaseModel):
    friend_id: int = Field(..., gt=0, description="ID друга для создания приватного чата")


# Output модели (response_model)
class MessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_id: int
    sender_name: str
    sender_avatar: Optional[str] = Field(None, description="URL аватара отправителя")
    content: str
    created_at: datetime
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    is_read: bool = False


class ChatItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str  # 'private', 'group'
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0

    # Для приватных чатов
    other_user_id: Optional[int] = None
    other_user_name: Optional[str] = None
    other_user_username: Optional[str] = None
    other_user_avatar: Optional[str] = None

    # Последнее сообщение
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    last_message_sender_id: Optional[int] = None


class ChatListResponse(BaseModel):
    chats: List[ChatItem]
    total: int


class SuccessResponse(BaseModel):
    message: str = "Операция выполнена успешно"


# Списки для response_model в роутере
class ChatListResponseModel(ChatListResponse):  # Обёртка для List[ChatItem]
    pass


class MessageListResponseModel(List[MessageItem]):  # List[MessageItem]
    pass
