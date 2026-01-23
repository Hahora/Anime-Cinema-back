import asyncio
import re
from typing import List, Dict, Any, Optional

from anime_parsers_ru import KodikParserAsync, ShikimoriParserAsync

# ═══════════════════════════════════════════
# SINGLETON ПАРСЕРЫ
# ═══════════════════════════════════════════

_kodik_parser: Optional[KodikParserAsync] = None
_shikimori_parser: Optional[ShikimoriParserAsync] = None
_parser_lock = asyncio.Lock()


async def get_kodik_parser() -> KodikParserAsync:
    """Singleton для Kodik парсера"""
    global _kodik_parser
    async with _parser_lock:
        if _kodik_parser is None:
            _kodik_parser = KodikParserAsync(validate_token=False)
        return _kodik_parser


async def get_shikimori_parser() -> ShikimoriParserAsync:
    """Singleton для Shikimori парсера"""
    global _shikimori_parser
    async with _parser_lock:
        if _shikimori_parser is None:
            _shikimori_parser = ShikimoriParserAsync()
        return _shikimori_parser


# Для обратной совместимости
async def get_parser() -> KodikParserAsync:
    return await get_kodik_parser()


# ═══════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════

def normalize_shikimori_id(raw_id: Any) -> Optional[str]:
    """Приводит shikimori_id к формату Kodik (z123)"""
    if raw_id is None:
        return None
    sid = str(raw_id)
    if not sid.startswith("z"):
        sid = f"z{sid}"
    return sid


def get_clean_shikimori_id(raw_id: Any) -> Optional[str]:
    """Получает чистый shikimori_id без префикса z (для Shikimori API)"""
    if raw_id is None:
        return None
    sid = str(raw_id)
    if sid.startswith("z"):
        sid = sid[1:]
    return sid


def normalize_search_text(text: str) -> str:
    """
    Нормализует текст для поиска:
    - Убирает [ТВ-1], [ТВ-2] и т.д.
    - Заменяет ё на е
    - Убирает лишние пробелы
    """
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def create_search_variants(text: str) -> List[str]:
    """
    Создаёт варианты поискового запроса для лучшего поиска:
    - "джо джо" → ["джо джо", "джоджо", "джо-джо"]
    - "ван пис" → ["ван пис", "ван-пис", "ванпис"]
    - "наруто" → ["наруто"]
    """
    text = normalize_search_text(text)
    variants = [text]

    words = text.split()

    if len(words) >= 2:
        # Вариант с дефисами: "ван пис" → "ван-пис"
        hyphenated = "-".join(words)
        if hyphenated not in variants:
            variants.append(hyphenated)

        # Вариант слитно: "джо джо" → "джоджо"
        joined = "".join(words)
        if joined not in variants:
            variants.append(joined)

        # Для двух одинаковых коротких слов: "джо джо" → особый случай
        if len(words) == 2 and words[0].lower() == words[1].lower():
            # "джо джо" → "джоджо" (уже добавлено выше)
            pass

    return variants


# ═══════════════════════════════════════════
# 🖼️ ПОЛУЧЕНИЕ ПОСТЕРА ИЗ SHIKIMORI
# ═══════════════════════════════════════════

async def get_poster_from_shikimori(shikimori_id: str) -> Optional[str]:
    """
    Получает постер аниме из Shikimori API
    
    Args:
        shikimori_id: ID аниме (с или без префикса 'z')
    
    Returns:
        URL постера или None
    """
    clean_id = get_clean_shikimori_id(shikimori_id)
    if not clean_id:
        return None

    try:
        parser = await get_shikimori_parser()

        # Используем deep_anime_info для получения постера
        info = await parser.deep_anime_info(
            shikimori_id=clean_id,
            return_parameters=['poster { originalUrl }']
        )

        if info and 'poster' in info:
            poster_data = info['poster']
            if isinstance(poster_data, dict):
                return poster_data.get('originalUrl')
            return poster_data

        return None

    except Exception as e:
        print(f"[SHIKIMORI POSTER ERROR] {e}")
        return None


async def get_posters_batch(shikimori_ids: List[str]) -> Dict[str, Optional[str]]:
    """
    Получает постеры для нескольких аниме (пакетный запрос)
    
    Args:
        shikimori_ids: Список ID аниме
    
    Returns:
        Словарь {shikimori_id: poster_url}
    """
    results = {}

    # Ограничиваем параллельные запросы чтобы не перегрузить Shikimori
    semaphore = asyncio.Semaphore(5)

    async def fetch_poster(sid: str):
        async with semaphore:
            # Добавляем небольшую задержку между запросами
            await asyncio.sleep(0.2)
            poster = await get_poster_from_shikimori(sid)
            results[sid] = poster

    tasks = [fetch_poster(sid) for sid in shikimori_ids if sid]
    await asyncio.gather(*tasks, return_exceptions=True)

    return results


# ─────────────────────────────────────────────
# 🔍 ПОИСК АНИМЕ
# ─────────────────────────────────────────────
async def search_anime(title: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Поиск аниме с группировкой по shikimori_id
    ✅ Постеры загружаются из Shikimori
    ✅ Умный поиск с вариантами запроса
    """
    parser = await get_kodik_parser()

    # Создаём варианты поискового запроса
    search_variants = create_search_variants(title)
    normalized_title = normalize_search_text(title)
    print(f"🔍 Ищем: '{title}' → варианты: {search_variants}")

    grouped: Dict[str, Dict] = {}
    search_words = set(normalized_title.lower().split())

    # Также создаём слитный вариант для сравнения
    search_joined = normalized_title.lower().replace(" ", "").replace("-", "")

    try:
        # Ищем по всем вариантам запроса
        for variant in search_variants:
            if len(grouped) >= limit:
                break

            try:
                results = await parser.search(
                    title=variant,
                    limit=limit * 15,
                    only_anime=True,
                    include_material_data=True,
                    strict=False
                )

                print(f"📊 Вариант '{variant}': Kodik вернул {len(results)} результатов")

                for item in results:
                    shiki_id = normalize_shikimori_id(item.get("shikimori_id"))
                    if not shiki_id:
                        continue

                    if shiki_id in grouped:
                        continue

                    material = item.get("material_data") or {}
                    title_ru = item.get("title", "")
                    title_orig = material.get("title_orig", "")

                    if not title_ru or len(title_ru) < 2:
                        continue

                    # Проверяем релевантность
                    normalized_anime_title = normalize_search_text(title_ru)
                    anime_words = set(normalized_anime_title.lower().split())

                    if title_orig:
                        normalized_orig_title = normalize_search_text(title_orig)
                        anime_words.update(normalized_orig_title.lower().split())

                    # Слитный вариант названия для сравнения
                    anime_title_joined = normalized_anime_title.lower().replace(" ", "").replace("-", "")

                    matching_words = search_words.intersection(anime_words)
                    relevance_ratio = len(matching_words) / len(search_words) if search_words else 0

                    is_relevant = (
                            relevance_ratio >= 0.4 or
                            normalized_title.lower() in normalized_anime_title.lower() or
                            normalized_anime_title.lower() in normalized_title.lower() or
                            search_joined in anime_title_joined or
                            anime_title_joined in search_joined
                    )

                    if not is_relevant:
                        continue

                    grouped[shiki_id] = {
                        "id": shiki_id,
                        "title": title_ru,
                        "title_orig": title_orig,
                        "year": item.get("year"),
                        "type": item.get("type"),
                        "poster": None,
                        "screenshots": item.get("screenshots", []),
                        "description": material.get("description"),
                        "genres": material.get("genres", []),
                        "status": material.get("status"),
                        "rating": material.get("shikimori_rating"),
                        "_relevance": relevance_ratio
                    }

                    if len(grouped) >= limit:
                        break

            except Exception as e:
                print(f"⚠️ Ошибка поиска варианта '{variant}': {e}")
                continue

        # ✅ Загружаем постеры из Shikimori
        if grouped:
            print(f"🖼️ Загружаем постеры из Shikimori для {len(grouped)} аниме...")
            posters = await get_posters_batch(list(grouped.keys()))

            for shiki_id, poster_url in posters.items():
                if shiki_id in grouped:
                    grouped[shiki_id]["poster"] = poster_url
                    # Fallback на скриншот если постер не найден
                    if not poster_url and grouped[shiki_id]["screenshots"]:
                        grouped[shiki_id]["poster"] = grouped[shiki_id]["screenshots"][0]

        # Сортируем по релевантности
        sorted_results = sorted(
            grouped.values(),
            key=lambda x: x.get("_relevance", 0),
            reverse=True
        )

        # Убираем служебные поля
        for r in sorted_results:
            r.pop("_relevance", None)
            r.pop("screenshots", None)

        print(f"✅ Итого найдено: {len(sorted_results)} релевантных результатов")

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
    ✅ Постер загружается из Shikimori
    """
    parser = await get_kodik_parser()
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

        # 3️⃣ Получаем постер из Shikimori
        print(f"🖼️ Загружаем постер из Shikimori для {shiki_id}...")
        poster = await get_poster_from_shikimori(shiki_id)

        # Fallback на скриншот
        if not poster and anime.get("screenshots"):
            poster = anime["screenshots"][0]

        # Обработка переводов
        translations = info.get("translations", [])
        seen_names = set()
        unique_translations = []

        for t in translations:
            name = t.get("name", "").strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_translations.append(t)

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
            "poster": poster,  # ✅ Постер из Shikimori
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
    parser = await get_kodik_parser()
    shiki_id = normalize_shikimori_id(shikimori_id)

    if not shiki_id:
        return None

    try:
        seria_num = episode_num if episode_num > 0 else 0

        url = await parser.get_m3u8_playlist_link(
            id=shiki_id,
            id_type="shikimori",
            seria_num=seria_num,
            translation_id=str(translation_id),
            quality=quality
        )

        if url and url.startswith("//"):
            url = f"https:{url}"

        return url

    except Exception as e:
        print(f"[KODIK VIDEO ERROR] {e}")
        return None


# ─────────────────────────────────────────────
# 🎭 АНИМЕ ПО ЖАНРУ
# ─────────────────────────────────────────────
async def get_anime_by_genre(genre: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Получение аниме по жанру с пагинацией
    ✅ Постеры загружаются из Shikimori
    """
    parser = await get_kodik_parser()

    try:
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

        pages_to_load = page * 3

        print(f"📄 Загружаем {pages_to_load} страниц из Kodik (page={page})")

        data, next_page = await parser.get_list(
            limit_per_page=100,
            pages_to_parse=pages_to_load,
            include_material_data=True,
            only_anime=True
        )

        print(f"📊 Получено из Kodik: {len(data)} записей")

        grouped: Dict[str, Dict] = {}

        for item in data:
            shiki_id = normalize_shikimori_id(item.get("shikimori_id"))
            if not shiki_id or shiki_id in grouped:
                continue

            material = item.get("material_data") or {}
            item_genres = material.get("genres", [])

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
                "poster": None,  # ← Заполним позже
                "screenshots": item.get("screenshots", []),
                "description": material.get("description"),
                "genres": item_genres,
                "status": material.get("status"),
                "rating": material.get("shikimori_rating")
            }

        all_results = list(grouped.values())

        # Пагинация
        offset = (page - 1) * per_page
        paginated = all_results[offset:offset + per_page]

        # ✅ Загружаем постеры только для текущей страницы
        if paginated:
            print(f"🖼️ Загружаем постеры из Shikimori для {len(paginated)} аниме...")
            poster_ids = [item["id"] for item in paginated]
            posters = await get_posters_batch(poster_ids)

            for item in paginated:
                poster_url = posters.get(item["id"])
                item["poster"] = poster_url
                # Fallback на скриншот
                if not poster_url and item.get("screenshots"):
                    item["poster"] = item["screenshots"][0]
                # Убираем скриншоты из ответа
                item.pop("screenshots", None)

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
    ✅ Постеры загружаются из Shikimori
    """
    parser = await get_kodik_parser()

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
                "poster": None,  # ← Заполним позже
                "screenshots": item.get("screenshots", []),
                "rating": material.get("shikimori_rating"),
                "status": material.get("status")
            }

            if len(grouped) >= limit:
                break

        results = list(grouped.values())

        # ✅ Загружаем постеры из Shikimori
        if results:
            print(f"🖼️ Загружаем постеры из Shikimori для {len(results)} аниме...")
            poster_ids = [item["id"] for item in results]
            posters = await get_posters_batch(poster_ids)

            for item in results:
                poster_url = posters.get(item["id"])
                item["poster"] = poster_url
                # Fallback на скриншот
                if not poster_url and item.get("screenshots"):
                    item["poster"] = item["screenshots"][0]
                # Убираем скриншоты из ответа
                item.pop("screenshots", None)

        return results

    except Exception as e:
        print(f"[KODIK TRENDING ERROR] {e}")
        return []
