from typing import List, Dict, Any, Optional

from app.core.genres import GENRES
from app.parsers.kodik_api import search_anime, get_trending_anime, get_anime_details, get_video_m3u8, \
    get_anime_by_genre


class AnimeService:
    def __init__(self):
        self._cache: Dict[str, Any] = {}

    async def search(self, title: str, limit: int = 12) -> List[Dict[str, Any]]:
        return await search_anime(title, limit)

    async def trending(self, limit: int = 12) -> List[Dict[str, Any]]:
        return await get_trending_anime(limit)

    async def details(self, shikimori_id: str) -> Optional[Dict[str, Any]]:
        result = await get_anime_details(shikimori_id)
        if not result:
            return None
        return result

    async def video_m3u8(self, shikimori_id: str, episode_num: int,
                         translation_id: str, quality: int = 720) -> Optional[str]:
        return await get_video_m3u8(shikimori_id, episode_num, translation_id, quality)

    def genres_list(self) -> List[Dict[str, str]]:
        return GENRES

    async def anime_by_genre(self, genre: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        return await get_anime_by_genre(genre, page, per_page)
