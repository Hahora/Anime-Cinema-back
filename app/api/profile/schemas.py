from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic.alias_generators import to_camel


class UserProfileBase(BaseModel):
    id: int = Field(..., description="ID пользователя")
    username: str = Field(..., min_length=3, max_length=20, description="Уникальный логин")
    name: str = Field(..., max_length=50, description="Отображаемое имя")
    avatar_url: Optional[str] = Field(None, description="URL аватара")
    cover_url: Optional[str] = Field(None, description="URL обложки")
    bio: Optional[str] = Field(None, max_length=500, description="Биография")
    created_at: datetime = Field(..., description="Дата регистрации")

    model_config = {
        "from_attributes": True,
        "alias_generator": to_camel,
        "populate_by_name": True,
    }


class UserProfile(UserProfileBase):
    message_privacy: str = Field("all", description="Приватность сообщений")
    total_anime: int = Field(0, ge=0, description="Всего аниме")
    total_episodes: int = Field(0, ge=0, description="Всего эпизодов")
    total_hours: int = Field(0, ge=0, description="Всего часов просмотра")
    favorites_count: int = Field(0, ge=0, description="Количество в избранном")

    @field_validator("message_privacy", mode="before")
    @classmethod
    def validate_privacy(cls, v: Optional[str]) -> str:
        if v not in ("all", "friendsonly", "nobody"):
            raise ValueError("message_privacy: 'all', 'friendsonly' или 'nobody'")
        return v


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None)
    cover_url: Optional[str] = Field(None)
    bio: Optional[str] = Field(None, max_length=500)
    message_privacy: Optional[str] = Field(None)

    model_config = {"from_attributes": True}

    @field_validator("message_privacy", mode="before")
    @classmethod
    def validate_privacy_update(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("all", "friendsonly", "nobody"):
            raise ValueError("message_privacy: 'all', 'friendsonly' или 'nobody'")
        return v


class ChangeUsername(BaseModel):
    new_username: str = Field(..., min_length=3, max_length=20, description="Новый логин")

    @field_validator("new_username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not (v.replace(".", "").replace("-", "").replace("_", "").isalnum()):
            raise ValueError("Username: буквы, цифры, ., -, _")
        return v.lower().strip()


class ChangePassword(BaseModel):
    current_password: str = Field(..., min_length=6, description="Старый пароль")
    new_password: str = Field(..., min_length=8, max_length=128, description="Новый пароль")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен быть не менее 8 символов")
        return v


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class UsernameUpdate(BaseModel):
    current_password: str
    new_username: str = Field(..., min_length=3, max_length=20)


class FullProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    username: Optional[UsernameUpdate] = None
    password: Optional[PasswordUpdate] = None
