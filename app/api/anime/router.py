from typing import Dict

from fastapi import APIRouter, HTTPException, status, Depends

from app.api.anime.schemas import SearchResponse, ListResponse, VideoResponse, GenreResponse, GenreAnimeResponse
from app.api.anime.service import AnimeService

router = APIRouter(prefix="/api/v1/anime", tags=["anime"])


@router.get("/search", response_model=SearchResponse)
async def api_search(title: str, limit: int = 12, service: AnimeService = Depends(AnimeService)):
    if not title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите название аниме")
    results = await service.search(title, limit)
    return SearchResponse(query=title, count=len(results), results=results)


@router.get("/trending", response_model=ListResponse)
async def api_trending(limit: int = 12, service: AnimeService = Depends(AnimeService)):
    results = await service.trending(limit)
    return ListResponse(count=len(results), results=results)


@router.get("/genres", response_model=GenreResponse)
async def get_genres(service: AnimeService = Depends(AnimeService)):
    genres = service.genres_list()
    return GenreResponse(genres=genres)


@router.get("/genres/{genre}/anime", response_model=GenreAnimeResponse)
async def get_anime_by_genre(genre: str, page: int = 1, limit: int = 10,
                             service: AnimeService = Depends(AnimeService)):
    try:
        data = await service.anime_by_genre(genre, page, limit)
        return GenreAnimeResponse(
            genre=genre, page=page, limit=limit,
            results=data["results"], has_more=data["has_more"]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка: {str(e)}")


@router.get("/video/{shikimori_id}/{episode_num}/{translation_id}", response_model=VideoResponse)
async def api_video(shikimori_id: str, episode_num: int, translation_id: str,
                    quality: int = 720, service: AnimeService = Depends(AnimeService)):
    url = await service.video_m3u8(shikimori_id, episode_num, translation_id, quality)
    if not url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео недоступно")
    return VideoResponse(m3u8_url=url, quality=quality, episode=episode_num, translation_id=translation_id)


@router.get("/{shikimori_id}", response_model=Dict)
async def api_anime(shikimori_id: str, service: AnimeService = Depends(AnimeService)):
    anime = await service.details(shikimori_id)
    if not anime:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аниме не найдено")
    return anime
