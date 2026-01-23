from typing import List

from pydantic import BaseModel


class OnlineUsersResponse(BaseModel):
    online_user_ids: List[int]
    count: int


class CanMessageResponse(BaseModel):
    can_message: bool
    reason: str | None = None


class UserOnlineResponse(BaseModel):
    user_id: int
    is_online: bool
