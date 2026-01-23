from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class FriendshipStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class FriendshipBase(BaseModel):
    friend_id: int = Field(..., gt=0, description="ID друга")


class FriendshipCreate(FriendshipBase):
    model_config = ConfigDict(from_attributes=True)


class UserShort(BaseModel):
    """Краткая информация о пользователе."""
    id: int = Field(gt=0)
    username: str = Field(min_length=1)
    name: str = Field(min_length=1)
    avatar_url: Optional[str] = Field(None, alias="avatar_url")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class FriendshipResponse(BaseModel):
    id: int = Field(gt=0)
    status: FriendshipStatus
    user: UserShort
    friend: UserShort
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
