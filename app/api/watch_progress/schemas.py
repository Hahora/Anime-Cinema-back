from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WatchedAnimeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WatchedAnimeUpdate(BaseModel):
    """Обновить прогресс просмотра аниме"""
    anime_id: str = Field(..., description="ID аниме")
    episodes_watched: int = Field(0, ge=0, description="Просмотренные эпизоды")
    total_episodes: int = Field(0, ge=0, description="Общее кол-во эпизодов")
    is_completed: bool = Field(False, description="Завершено ли")


class WatchedAnimeItem(WatchedAnimeBase):
    """Просмотренное аниме"""
    id: int
    anime_id: str
    episodes_watched: int
    total_episodes: int
    is_completed: bool
    last_watched: datetime
    title: Optional[str] = Field(None, description="Название аниме")
    poster: Optional[str] = Field(None, description="Постер URL")


class WatchHistoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WatchHistoryAdd(BaseModel):
    """Добавить запись в историю просмотра"""
    anime_id: str = Field(..., description="ID аниме")
    episode_num: int = Field(..., gt=0, description="Номер эпизода")
    progress_seconds: int = Field(0, ge=0, description="Прогресс в секундах")
    duration_seconds: int = Field(0, ge=0, description="Длительность эпизода")
    title: Optional[str] = None
    poster: Optional[str] = None
    translation_id: Optional[str] = None


class WatchHistoryItem(WatchHistoryBase):
    """Запись истории просмотра"""
    id: int
    anime_id: str
    episode_num: int
    progress_seconds: int
    duration_seconds: int
    watched_at: datetime
    title: Optional[str] = Field(None, description="Название аниме")
    poster: Optional[str] = Field(None, description="Постер URL")
    translation_id: Optional[str] = Field(None, description="ID перевода")
