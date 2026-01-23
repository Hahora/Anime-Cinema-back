from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPTED = "friend_accepted"
    MESSAGE = "message"
    LIKE = "like"
    COMMENT = "comment"


class NotificationItem(BaseModel):
    id: int = Field(..., description="Уникальный ID уведомления", example=1)
    type: NotificationType = Field(..., description="Тип уведомления", example="friend_request")
    title: str = Field(..., description="Заголовок", max_length=100, example="Новый запрос в друзья")
    message: str = Field(..., description="Текст сообщения", max_length=500, example="Иван пригласил вас в друзья")
    sender_id: Optional[int] = Field(None, description="ID отправителя", example=42)
    sender_name: Optional[str] = Field(None, description="Имя отправителя", example="Иван Иванов")
    sender_avatar: Optional[str] = Field(None, description="Аватар отправителя (URL)",
                                         example="https://example.com/avatar.jpg")
    is_read: bool = Field(default=False, description="Прочитано ли", example=False)
    created_at: datetime = Field(..., description="Дата создания")

    model_config = ConfigDict(from_attributes=True)
