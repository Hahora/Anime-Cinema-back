from typing import List, Dict, Any

from pydantic import BaseModel


class SearchResponse(BaseModel):
    query: str
    count: int
    results: List[Dict[str, Any]]


class ListResponse(BaseModel):
    count: int
    results: List[Dict[str, Any]]


class VideoResponse(BaseModel):
    m3u8_url: str
    quality: int
    episode: int
    translation_id: str


class GenreResponse(BaseModel):
    genres: List[Dict[str, str]]


class GenreAnimeResponse(BaseModel):
    genre: str
    page: int
    limit: int
    results: List[Dict[str, Any]]
    has_more: bool
