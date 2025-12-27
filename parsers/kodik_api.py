import re
from typing import List, Dict, Any, Optional
from anime_parsers_ru import KodikParserAsync
import asyncio


_parser: Optional[KodikParserAsync] = None
_parser_lock = asyncio.Lock()


async def get_parser() -> KodikParserAsync:
    """Singleton для парсера"""
    global _parser
    async with _parser_lock:
        if _parser is None:
            _parser = KodikParserAsync(validate_token=False)
        return _parser


def normalize_shikimori_id(raw_id: Any) -> Optional[str]:
    """Приводит shikimori_id к формату Kodik (z123)"""
    if raw_id is None:
        return None
    sid = str(raw_id)
    if not sid.startswith("z"):
        sid = f"z{sid}"
    return sid


def normalize_search_text(text: str) -> str:
    """
    Нормализует текст для поиска:
    - Убирает [ТВ-1], [ТВ-2] и т.д.
    - Заменяет ё на е
    - Убирает лишние пробелы
    """
    # Убираем части типа [ТВ-1], [ТВ-2], [OVA] и т.д.
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)
    
    # Заменяем ё на е
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# ─────────────────────────────────────────────
# 🔍 ПОИСК АНИМЕ
# ─────────────────────────────────────────────
async def search_anime(title: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Поиск аниме с группировкой по shikimori_id
    """
    parser = await get_parser()

    # ✅ Нормализуем поисковый запрос
    normalized_title = normalize_search_text(title)
    print(f"🔍 Ищем: '{title}' → нормализовано: '{normalized_title}'")

    try:
        # ✅ Убрали strict=True для более гибкого поиска
        results = await parser.search(
            title=normalized_title,
            limit=limit * 20,  # ✅ Увеличили запас для фильтрации
            only_anime=True,
            include_material_data=True,
            strict=False  # ✅ Более гибкий поиск
        )

        print(f"📊 Kodik вернул: {len(results)} результатов")

        # Группируем по shikimori_id
        grouped: Dict[str, Dict] = {}

        # ✅ Нормализованный запрос для сравнения
        search_words = set(normalized_title.lower().split())

        for item in results:
            shiki_id = normalize_shikimori_id(item.get("shikimori_id"))
            if not shiki_id:
                continue

            # Если уже есть — пропускаем дубликаты
            if shiki_id in grouped:
                continue

            material = item.get("material_data") or {}
            title_ru = item.get("title", "")
            title_orig = material.get("title_orig", "")
            
            # Фильтруем очевидные дубликаты и неподходящие
            if not title_ru or len(title_ru) < 2:
                continue

            # ✅ Проверяем релевантность
            # Нормализуем название аниме
            normalized_anime_title = normalize_search_text(title_ru)
            anime_words = set(normalized_anime_title.lower().split())
            
            # Проверяем также оригинальное название
            if title_orig:
                normalized_orig_title = normalize_search_text(title_orig)
                anime_words.update(normalized_orig_title.lower().split())
            
            # Считаем совпадающие слова
            matching_words = search_words.intersection(anime_words)
            
            # Если хотя бы 50% слов совпадают или это точное вхождение
            relevance_ratio = len(matching_words) / len(search_words) if search_words else 0
            
            # ✅ Более мягкий фильтр релевантности
            is_relevant = (
                relevance_ratio >= 0.4 or  # 40% слов совпадают
                normalized_title.lower() in normalized_anime_title.lower() or
                normalized_anime_title.lower() in normalized_title.lower()
            )
            
            if not is_relevant:
                continue

            grouped[shiki_id] = {
                "id": shiki_id,
                "title": title_ru,
                "title_orig": title_orig,
                "year": item.get("year"),
                "type": item.get("type"),
                "poster": item["screenshots"][0] if item.get("screenshots") else None,
                "description": material.get("description"),
                "genres": material.get("genres", []),
                "status": material.get("status"),
                "rating": material.get("shikimori_rating"),
                "_relevance": relevance_ratio  # Для отладки
            }

            if len(grouped) >= limit:
                break

        # ✅ Сортируем по релевантности
        sorted_results = sorted(
            grouped.values(),
            key=lambda x: x.get("_relevance", 0),
            reverse=True
        )
        
        # Убираем служебное поле
        for r in sorted_results:
            r.pop("_relevance", None)
        
        print(f"✅ Отфильтровано: {len(sorted_results)} релевантных результатов")

        return sorted_results[:limit]

    except Exception as e:
        print(f"[KODIK SEARCH ERROR] {e}")
        return []


# ─────────────────────────────────────────────
# 📄 ИНФОРМАЦИЯ ОБ АНИМЕ
# ─────────────────────────────────────────────
async def get_anime_details(shikimori_id: str) -> Optional[Dict[str, Any]]:
    """
    Получение детальной информации об аниме
    """
    parser = await get_parser()
    shiki_id = normalize_shikimori_id(shikimori_id)

    if not shiki_id:
        return None

    try:
        # 1️⃣ Переводы и количество серий
        info = await parser.get_info(
            id=shiki_id,
            id_type="shikimori"
        )

        # 2️⃣ Основные данные
        search_result = await parser.search_by_id(
            id=shiki_id,
            id_type="shikimori",
            limit=1
        )

        if not search_result:
            return None

        anime = search_result[0]
        material = anime.get("material_data") or {}

        # Обработка переводов - убираем дубликаты и сортируем
        translations = info.get("translations", [])
        seen_names = set()
        unique_translations = []
        
        for t in translations:
            name = t.get("name", "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_translations.append(t)

        # Сортируем переводы по популярности
        popular_studios = ["AniLibria", "AniDUB", "Animedia", "AniStar"]
        unique_translations.sort(
            key=lambda x: (
                popular_studios.index(x["name"]) if x["name"] in popular_studios else 999,
                -int(x.get("id", 0))
            )
        )

        return {
            "id": shiki_id,
            "title": anime.get("title"),
            "title_orig": material.get("title_orig"),
            "description": material.get("description"),
            "genres": material.get("genres", []),
            "type": anime.get("type"),
            "status": material.get("status"),
            "episodes_count": material.get("episodes_total"),
            "episodes_aired": material.get("episodes_aired"),
            "series_count": info.get("series_count", 1),
            "year": anime.get("year"),
            "rating": material.get("shikimori_rating"),
            "poster": anime["screenshots"][0] if anime.get("screenshots") else None,
            "screenshots": anime.get("screenshots", []),
            "translations": unique_translations,
            "next_episode_at": material.get("next_episode_at"),
            "duration": material.get("duration")
        }

    except Exception as e:
        print(f"[KODIK DETAILS ERROR] {e}")
        return None


# ─────────────────────────────────────────────
# 🎬 M3U8 ВИДЕО
# ─────────────────────────────────────────────
async def get_video_m3u8(
    shikimori_id: str,
    episode_num: int,
    translation_id: str,
    quality: int = 720
) -> Optional[str]:
    """
    Получение прямой ссылки на m3u8 плейлист
    """
    parser = await get_parser()
    shiki_id = normalize_shikimori_id(shikimori_id)

    if not shiki_id:
        return None

    try:
        # Для фильмов или одной серии - используем 0
        seria_num = episode_num if episode_num > 0 else 0

        url = await parser.get_m3u8_playlist_link(
            id=shiki_id,
            id_type="shikimori",
            seria_num=seria_num,
            translation_id=str(translation_id),
            quality=quality
        )

        # Добавляем протокол если нужно
        if url and url.startswith("//"):
            url = f"https:{url}"

        return url

    except Exception as e:
        print(f"[KODIK VIDEO ERROR] {e}")
        return None
    

async def get_anime_by_genre(genre: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Получение аниме по жанру с ЛЕНИВОЙ загрузкой
    Каждый раз загружаем новую порцию из Kodik
    """
    parser = await get_parser()

    try:
        # ✅ Маппинг жанров - РАСШИРЕННЫЙ
        genre_lower = genre.lower()
        genre_mapping = {
            "экшен": ["action", "экшен", "экшн", "боевик"],
            "приключения": ["adventure", "приключения"],
            "комедия": ["comedy", "комедия"],
            "драма": ["drama", "драма"],
            "фэнтези": ["fantasy", "фэнтези"],
            "романтика": ["romance", "романтика", "мелодрама"],
            "sci-fi": ["sci-fi", "фантастика", "научная фантастика"],
            "триллер": ["thriller", "триллер"],
            "мистика": ["mystery", "мистика"],
            "психология": ["psychological", "психология"],
            "школа": ["school", "школа"],
            "спорт": ["sports", "спорт"],
            "сёнэн": ["shounen", "сёнэн", "shonen"],
            "сёдзё": ["shoujo", "сёдзё", "shojo"],
            "сэйнэн": ["seinen", "сэйнэн"],
            "меха": ["mecha", "меха"],
            "музыка": ["music", "музыка"],
            "детектив": ["detective", "детектив"],
            "ужасы": ["horror", "ужасы"],
            "повседневность": ["slice of life", "повседневность"],
            "военное": ["military", "военное"],
            "история": ["historical", "история"],
            "безумие": ["dementia", "безумие"],
            "демоны": ["demons", "демоны"],
            "игры": ["game", "игры"],
            "магия": ["magic", "магия"],
            "пародия": ["parody", "пародия"],
            "самураи": ["samurai", "самураи"],
            "супер сила": ["super power", "супер сила"],
            "вампиры": ["vampire", "вампиры"],
        }

        search_genres = genre_mapping.get(genre_lower, [genre_lower])
        
        # ✅ Загружаем МНОГО страниц, чтобы после фильтрации осталось достаточно
        # Например: запросили 10 аниме, но после фильтра может остаться 3-5
        # Поэтому загружаем с запасом
        pages_to_load = page * 3  # Множитель для запаса
        
        print(f"📄 Загружаем {pages_to_load} страниц из Kodik (page={page})")

        data, next_page = await parser.get_list(
            limit_per_page=100,
            pages_to_parse=pages_to_load,
            include_material_data=True,
            only_anime=True
        )

        print(f"📊 Получено из Kodik: {len(data)} записей")

        # ✅ Фильтруем по жанру
        grouped: Dict[str, Dict] = {}
        
        for item in data:
            shiki_id = normalize_shikimori_id(item.get("shikimori_id"))
            if not shiki_id or shiki_id in grouped:
                continue

            material = item.get("material_data") or {}
            item_genres = material.get("genres", [])
            
            # Проверяем совпадение жанра
            genre_match = any(
                any(search.lower() in g.lower() for g in item_genres)
                for search in search_genres
            )

            if not genre_match:
                continue

            grouped[shiki_id] = {
                "id": shiki_id,
                "title": item.get("title"),
                "title_orig": material.get("title_orig"),
                "year": item.get("year"),
                "type": item.get("type"),
                "poster": item["screenshots"][0] if item.get("screenshots") else None,
                "description": material.get("description"),
                "genres": item_genres,
                "status": material.get("status"),
                "rating": material.get("shikimori_rating")
            }

        all_results = list(grouped.values())
        
        # ✅ Вычисляем offset для пагинации
        offset = (page - 1) * per_page
        paginated = all_results[offset:offset + per_page]
        
        # ✅ Проверяем есть ли ещё результаты
        has_more = len(all_results) > offset + per_page or next_page is not None
        
        print(f"✅ Жанр '{genre}': отфильтровано {len(all_results)}, возвращаем {len(paginated)}")
        
        return {
            "results": paginated,
            "has_more": has_more,
            "current_page": page
        }

    except Exception as e:
        print(f"[KODIK GENRE ERROR] {e}")
        return {"results": [], "has_more": False, "current_page": page}


# ─────────────────────────────────────────────
# 🔥 ПОПУЛЯРНЫЕ АНИМЕ
# ─────────────────────────────────────────────
async def get_trending_anime(limit: int = 12) -> List[Dict[str, Any]]:
    """
    Получение списка популярных аниме
    """
    parser = await get_parser()

    try:
        data, _ = await parser.get_list(
            limit_per_page=limit * 5,
            pages_to_parse=1,
            include_material_data=True,
            only_anime=True
        )

        grouped: Dict[str, Dict] = {}

        for item in data:
            shiki_id = normalize_shikimori_id(item.get("shikimori_id"))
            if not shiki_id or shiki_id in grouped:
                continue

            material = item.get("material_data") or {}
            
            grouped[shiki_id] = {
                "id": shiki_id,
                "title": item.get("title"),
                "year": item.get("year"),
                "type": item.get("type"),
                "poster": item["screenshots"][0] if item.get("screenshots") else None,
                "rating": material.get("shikimori_rating"),
                "status": material.get("status")
            }

            if len(grouped) >= limit:
                break

        return list(grouped.values())

    except Exception as e:
        print(f"[KODIK TRENDING ERROR] {e}")
        return []