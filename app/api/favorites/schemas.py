from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class FavoriteAdd(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anime_id: str = Field(..., min_length=1, description="ID аниме")
    title: Optional[str] = Field(None, max_length=255, description="Название аниме")
    poster: Optional[str] = Field(None, description="URL постера")
    year: Optional[int] = Field(None, ge=1900, le=2030, description="Год выпуска")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Рейтинг")


class FavoriteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anime_id: str
    title: Optional[str]
    poster: Optional[str]
    year: Optional[int]
    rating: Optional[float]
    added_at: datetime
