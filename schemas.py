from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════
# АВТОРИЗАЦИЯ
# ═══════════════════════════════════════════

class UserRegister(BaseModel):
    """Данные для регистрации"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=72)  # ИСПРАВЛЕНО: max 72
    name: str = Field(..., min_length=2, max_length=100)
    admin_key: str
    
    @validator('username')
    def username_alphanumeric(cls, v):
        """Только буквы, цифры, _ и -"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Неверный формат username')
        return v.lower()
    
    @validator('password')
    def password_strength(cls, v):
        """Проверка силы пароля"""
        if len(v) < 8:
            raise ValueError('Пароль должен быть минимум 8 символов')
        if len(v) > 72:
            raise ValueError('Пароль не должен превышать 72 символа (ограничение bcrypt)')
        return v


class UserLogin(BaseModel):
    """Данные для входа"""
    username: str
    password: str


class Token(BaseModel):
    """JWT токен"""
    access_token: str
    token_type: str = "bearer"


# ═══════════════════════════════════════════
# ПРОФИЛЬ
# ═══════════════════════════════════════════

class UserProfile(BaseModel):
    """Профиль пользователя"""
    id: int
    username: str
    name: str
    avatar_url: str
    cover_url: str
    bio: str
    created_at: datetime
    
    # Статистика
    total_anime: int = 0
    total_episodes: int = 0
    total_hours: int = 0
    favorites_count: int = 0

    class Config:
        from_attributes = True  # Для SQLAlchemy моделей


class UserProfileUpdate(BaseModel):
    """Обновление профиля"""
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    bio: Optional[str] = None


# ═══════════════════════════════════════════
# ИЗБРАННОЕ
# ═══════════════════════════════════════════

class FavoriteAdd(BaseModel):
    """Добавить в избранное"""
    anime_id: str
    title: Optional[str] = None
    poster: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None


class FavoriteItem(BaseModel):
    """Элемент избранного"""
    id: int
    anime_id: str
    title: Optional[str]
    poster: Optional[str]
    year: Optional[int]
    rating: Optional[float]
    added_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# ПРОСМОТРЕННОЕ
# ═══════════════════════════════════════════

class WatchedAnimeUpdate(BaseModel):
    """Обновить прогресс"""
    anime_id: str
    episodes_watched: int = 0
    total_episodes: int = 0
    is_completed: bool = False
    title: Optional[str] = None
    poster: Optional[str] = None


class WatchedAnimeItem(BaseModel):
    """Просмотренное аниме"""
    id: int
    anime_id: str
    title: Optional[str]
    poster: Optional[str]
    episodes_watched: int
    total_episodes: int
    is_completed: bool
    last_watched: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# ИСТОРИЯ
# ═══════════════════════════════════════════

class WatchHistoryAdd(BaseModel):
    """Добавить в историю"""
    anime_id: str
    episode_num: int
    progress_seconds: int = 0
    duration_seconds: int = 0
    title: Optional[str] = None
    poster: Optional[str] = None
    translation_id: Optional[str] = None


class WatchHistoryItem(BaseModel):
    """Запись истории"""
    id: int
    anime_id: str
    episode_num: int
    title: Optional[str]
    poster: Optional[str]
    progress_seconds: int
    duration_seconds: int
    translation_id: Optional[str]
    watched_at: datetime

    class Config:
        from_attributes = True

# ДРУЗЬЯ
# ═══════════════════════════════════════════

class UserShort(BaseModel):
    """Краткая информация о пользователе"""
    id: int
    username: str
    name: str
    avatar_url: Optional[str]
    
    class Config:
        from_attributes = True


class FriendshipBase(BaseModel):
    friend_id: int


class FriendshipCreate(FriendshipBase):
    pass


class FriendshipItem(BaseModel):
    id: int
    user_id: int
    friend_id: int
    status: str
    created_at: datetime
    friend: UserShort  # Информация о друге
    
    class Config:
        from_attributes = True


class FriendshipResponse(BaseModel):
    id: int
    status: str
    user: UserShort
    friend: UserShort
    created_at: datetime
    
    class Config:
        from_attributes = True        

class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    message: str
    sender_id: Optional[int]
    sender_name: Optional[str]
    sender_avatar: Optional[str]
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True        

# ═══════════════════════════════════════════
# AUTH - БЕЗОПАСНОСТЬ
# ═══════════════════════════════════════════

class ChangeUsername(BaseModel):
    new_username: str
    
    @validator('new_username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Логин должен быть не менее 3 символов')
        if len(v) > 20:
            raise ValueError('Логин должен быть не более 20 символов')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Логин может содержать только буквы, цифры, _ и -')
        return v.lower()


class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Пароль должен быть не менее 6 символов')
        return v