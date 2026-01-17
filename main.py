from fastapi import FastAPI, HTTPException, Depends, status, Request  
from fastapi.responses import JSONResponse 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text, or_, and_
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
import socketio

from database import get_db
from models import User, Favorite, WatchedAnime, WatchHistory, Friendship, Notification, Chat, ChatParticipant, Message, MessageEditHistory
from schemas import (
    UserRegister, Token, UserProfile, UserProfileUpdate,
    FavoriteAdd, FavoriteItem,
    WatchedAnimeUpdate, WatchedAnimeItem,
    WatchHistoryAdd, WatchHistoryItem,
    UserShort, FriendshipCreate, FriendshipItem, FriendshipResponse, NotificationItem,
    ChangeUsername, ChangePassword,
    ChatCreate, ChatItem, MessageCreate, MessageItem
)
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_active_user, verify_admin_key
)

# Импорт парсера аниме
from parsers.kodik_api import (
    search_anime,
    get_anime_details,
    get_video_m3u8,
    get_trending_anime,
    get_anime_by_genre 
)

from websocket_manager import (
    sio,
    send_friend_request_notification,
    send_friend_accepted_notification,
    send_friend_rejected_notification,
    get_connection_stats
)

app = FastAPI(
    title="Anime Cinema API",
    version="3.0.0",
    description="API для просмотра аниме через Kodik с авторизацией и WebSocket уведомлениями"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(
    sio,
    app,
)

# ═══════════════════════════════════════════
# ROOT & HEALTH
# ═══════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Anime Cinema API",
        "version": "3.0.0",
        "database": "PostgreSQL",
        "features": ["auth", "profiles", "favorites", "history", "websocket"]
    }
@app.get("/api/debug/privacy/{user_id}")
async def debug_privacy(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    return {
        "username": user.username,
        "message_privacy": user.message_privacy,
        "is_null": user.message_privacy is None,
        "effective": user.message_privacy or "all"
    }
@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    """Проверка работоспособности"""
    try:
        db.connection()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {
            "status": "unhealthy", 
            "database": "disconnected", 
            "error": str(e)
        }


@app.get("/api/websocket/stats")
async def websocket_stats(current_user: User = Depends(get_current_active_user)):
    """Статистика WebSocket подключений"""
    return get_connection_stats()


# ═══════════════════════════════════════════
# АВТОРИЗАЦИЯ
# ═══════════════════════════════════════════

@app.post("/api/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Регистрация нового пользователя (только с админским ключом!)"""
    if not verify_admin_key(user_data.admin_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный ключ регистрации"
        )
    
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует"
        )
    
    new_user = User(
        username=user_data.username.lower(),
        name=user_data.name,
        hashed_password=get_password_hash(user_data.password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.username})
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Вход в систему"""
    user = db.query(User).filter(User.username == form_data.username.lower()).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    
    return {"access_token": access_token, "token_type": "bearer"}


# ═══════════════════════════════════════════
# ПРОФИЛЬ
# ═══════════════════════════════════════════

@app.get("/api/profile/me", response_model=UserProfile)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение профиля текущего пользователя
    ✅ Теперь возвращает message_privacy
    """
    from sqlalchemy import func
    
    stats = db.query(
        func.count(WatchedAnime.id).label('total'),
        func.coalesce(func.sum(WatchedAnime.episodes_watched), 0).label('episodes')
    ).filter(WatchedAnime.user_id == current_user.id).first()
    
    favorites_count = db.query(func.count(Favorite.id)).filter(
        Favorite.user_id == current_user.id
    ).scalar()
    
    total_hours = int((stats.episodes * 24) // 60)
    
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        cover_url=current_user.cover_url,
        bio=current_user.bio,
        created_at=current_user.created_at,
        message_privacy=current_user.message_privacy or "all",
        total_anime=stats.total or 0,
        total_episodes=int(stats.episodes),
        total_hours=total_hours,
        favorites_count=favorites_count or 0
    )


@app.put("/api/profile/me", response_model=UserProfile)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Обновляем только переданные поля
    for key, value in profile_data.dict(exclude_unset=True).items():
        setattr(current_user, key, value)
    
    db.commit()
    db.refresh(current_user)
    
    # Возвращаем обновленный профиль
    return await get_my_profile(current_user, db)

# Добавьте этот эндпоинт после /api/profile/me

@app.get("/api/profile/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение профиля любого пользователя (публичная информация)
    """
    # Ищем пользователя
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Подсчёт статистики
    stats = db.query(
        func.count(WatchedAnime.id).label('total'),
        func.coalesce(func.sum(WatchedAnime.episodes_watched), 0).label('episodes')
    ).filter(WatchedAnime.user_id == user.id).first()
    
    favorites_count = db.query(func.count(Favorite.id)).filter(
        Favorite.user_id == user.id
    ).scalar()
    
    total_hours = int((stats.episodes * 24) // 60)
    
    return UserProfile(
        id=user.id,
        username=user.username,
        name=user.name,
        avatar_url=user.avatar_url,
        cover_url=user.cover_url,
        bio=user.bio,
        created_at=user.created_at,
        total_anime=stats.total or 0,
        total_episodes=int(stats.episodes) if stats.episodes else 0,
        total_hours=total_hours,
        favorites_count=favorites_count or 0
    )


# Также добавьте эндпоинты для получения чужого избранного и истории

@app.get("/api/profile/{user_id}/favorites", response_model=List[FavoriteItem])
async def get_user_favorites(
    user_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение избранного другого пользователя"""
    # Проверяем существование пользователя
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    favorites = db.query(Favorite).filter(
        Favorite.user_id == user_id
    ).order_by(desc(Favorite.added_at)).limit(limit).all()
    
    return favorites


@app.get("/api/profile/{user_id}/history", response_model=List[WatchHistoryItem])
async def get_user_history(
    user_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение истории другого пользователя"""
    # Проверяем существование пользователя
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    history = db.query(WatchHistory).filter(
        WatchHistory.user_id == user_id
    ).order_by(desc(WatchHistory.watched_at)).limit(limit).all()
    
    return history

# ═══════════════════════════════════════════
# ЖАНРЫ
# ═══════════════════════════════════════════

@app.get("/api/genres")
async def get_genres():
    """
    Получить список всех доступных жанров
    Публичный эндпоинт (не требует авторизации)
    """
    genres = [
        {"name": "Экшен", "slug": "экшен", "icon": "⚔️"},
        {"name": "Приключения", "slug": "приключения", "icon": "🗺️"},
        {"name": "Комедия", "slug": "комедия", "icon": "😂"},
        {"name": "Драма", "slug": "драма", "icon": "🎭"},
        {"name": "Фэнтези", "slug": "фэнтези", "icon": "🔮"},
        {"name": "Романтика", "slug": "романтика", "icon": "💕"},
        {"name": "Sci-Fi", "slug": "sci-fi", "icon": "🚀"},
        {"name": "Триллер", "slug": "триллер", "icon": "🔪"},
        {"name": "Мистика", "slug": "мистика", "icon": "👻"},
        {"name": "Психология", "slug": "психология", "icon": "🧠"},
        {"name": "Школа", "slug": "школа", "icon": "🏫"},
        {"name": "Спорт", "slug": "спорт", "icon": "⚽"},
        {"name": "Сёнэн", "slug": "сёнэн", "icon": "👊"},
        {"name": "Сёдзё", "slug": "сёдзё", "icon": "🌸"},
        {"name": "Сэйнэн", "slug": "сэйнэн", "icon": "🎯"},
        {"name": "Меха", "slug": "меха", "icon": "🤖"},
        {"name": "Музыка", "slug": "музыка", "icon": "🎵"},
        {"name": "Детектив", "slug": "детектив", "icon": "🔍"},
        {"name": "Ужасы", "slug": "ужасы", "icon": "😱"},
        {"name": "Повседневность", "slug": "повседневность", "icon": "☕"},
        {"name": "Военное", "slug": "военное", "icon": "🎖️"},
        {"name": "История", "slug": "история", "icon": "📜"},
        {"name": "Безумие", "slug": "безумие", "icon": "🌀"},
        {"name": "Демоны", "slug": "демоны", "icon": "😈"},
        {"name": "Игры", "slug": "игры", "icon": "🎮"},
        {"name": "Магия", "slug": "магия", "icon": "✨"},
        {"name": "Пародия", "slug": "пародия", "icon": "🤡"},
        {"name": "Самураи", "slug": "самураи", "icon": "🗡️"},
        {"name": "Супер сила", "slug": "супер сила", "icon": "💪"},
        {"name": "Вампиры", "slug": "вампиры", "icon": "🧛"},
    ]
    
    return genres


@app.get("/api/genres/{genre}/anime")
async def get_anime_by_genre_endpoint(
    genre: str,
    page: int = 1,      # ✅ Теперь используем page вместо offset
    limit: int = 10
):
    """
    Получить аниме по жанру с пагинацией
    
    page=1 → первые 10
    page=2 → следующие 10
    page=3 → ещё 10
    и так далее...
    """
    try:
        data = await get_anime_by_genre(genre, page=page, per_page=limit)
        
        return {
            "genre": genre,
            "page": page,
            "limit": limit,
            "results": data["results"],
            "has_more": data["has_more"]
        }
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аниме: {str(e)}"
        )


# ═══════════════════════════════════════════
# ИЗБРАННОЕ
# ═══════════════════════════════════════════

@app.get("/api/favorites", response_model=List[FavoriteItem])
async def get_favorites(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Список избранного"""
    return db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).order_by(desc(Favorite.added_at)).limit(limit).all()


@app.post("/api/favorites", response_model=FavoriteItem, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    data: FavoriteAdd,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Добавить в избранное"""
    if db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.anime_id == data.anime_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Уже в избранном"
        )
    
    new_fav = Favorite(user_id=current_user.id, **data.dict())
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    
    return new_fav


@app.delete("/api/favorites/{anime_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    anime_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить из избранного"""
    deleted = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.anime_id == anime_id
    ).delete()
    
    db.commit()
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не найдено"
        )


@app.get("/api/favorites/check/{anime_id}")
async def check_favorite(
    anime_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Проверить, в избранном ли аниме"""
    exists = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.anime_id == anime_id
    ).first() is not None
    
    return {"is_favorite": exists}


# ═══════════════════════════════════════════
# ПРОСМОТРЕННОЕ
# ═══════════════════════════════════════════

@app.get("/api/watched", response_model=List[WatchedAnimeItem])
async def get_watched(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Список просмотренного"""
    return db.query(WatchedAnime).filter(
        WatchedAnime.user_id == current_user.id
    ).order_by(desc(WatchedAnime.last_watched)).limit(limit).all()


@app.post("/api/watched", response_model=WatchedAnimeItem)
async def update_watched(
    data: WatchedAnimeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Обновить прогресс просмотра"""
    watched = db.query(WatchedAnime).filter(
        WatchedAnime.user_id == current_user.id,
        WatchedAnime.anime_id == data.anime_id
    ).first()
    
    if watched:
        for key, value in data.dict(exclude={'anime_id'}).items():
            setattr(watched, key, value)
        watched.last_watched = func.now()
    else:
        watched = WatchedAnime(user_id=current_user.id, **data.dict())
        db.add(watched)
    
    db.commit()
    db.refresh(watched)
    
    return watched


@app.get("/api/watched/check/{anime_id}")
async def check_watched(
    anime_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Проверить статус просмотра"""
    watched = db.query(WatchedAnime).filter(
        WatchedAnime.user_id == current_user.id,
        WatchedAnime.anime_id == anime_id
    ).first()
    
    if not watched:
        return {
            "is_watched": False,
            "episodes_watched": 0,
            "is_completed": False
        }
    
    return {
        "is_watched": True,
        "episodes_watched": watched.episodes_watched,
        "total_episodes": watched.total_episodes,
        "is_completed": watched.is_completed
    }


# ═══════════════════════════════════════════
# ИСТОРИЯ ПРОСМОТРОВ
# ═══════════════════════════════════════════

@app.get("/api/history", response_model=List[WatchHistoryItem])
async def get_history(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """История просмотров"""
    return db.query(WatchHistory).filter(
        WatchHistory.user_id == current_user.id
    ).order_by(desc(WatchHistory.watched_at)).limit(limit).all()


@app.post("/api/history", response_model=WatchHistoryItem)
async def add_history(
    data: WatchHistoryAdd,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Добавить в историю"""
    history = db.query(WatchHistory).filter(
        WatchHistory.user_id == current_user.id,
        WatchHistory.anime_id == data.anime_id,
        WatchHistory.episode_num == data.episode_num
    ).first()
    
    if history:
        history.watched_at = func.now()
        history.progress_seconds = data.progress_seconds
        history.duration_seconds = data.duration_seconds
    else:
        history = WatchHistory(user_id=current_user.id, **data.dict())
        db.add(history)
    
    db.commit()
    db.refresh(history)
    
    return history


# ═══════════════════════════════════════════
# АНИМЕ (KODIK API) - ПУБЛИЧНЫЕ ЭНДПОИНТЫ
# ═══════════════════════════════════════════

@app.get("/api/search")
async def api_search(title: str, limit: int = 12):
    """
    Поиск аниме по названию
    Публичный эндпоинт (не требует авторизации)
    """
    if not title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Введите название аниме"
        )
    
    results = await search_anime(title, limit)
    
    return {
        "query": title,
        "count": len(results),
        "results": results
    }


@app.get("/api/trending")
async def api_trending(limit: int = 12):
    """
    Популярные аниме
    Публичный эндпоинт (не требует авторизации)
    """
    results = await get_trending_anime(limit)
    
    return {
        "count": len(results),
        "results": results
    }


@app.get("/api/anime/{shikimori_id}")
async def api_anime(shikimori_id: str):
    """
    Детальная информация об аниме
    Публичный эндпоинт (не требует авторизации)
    """
    anime = await get_anime_details(shikimori_id)
    
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Аниме не найдено"
        )
    
    return anime


@app.get("/api/video/{shikimori_id}/{episode_num}/{translation_id}")
async def api_video(
    shikimori_id: str,
    episode_num: int,
    translation_id: str,
    quality: Optional[int] = 720
):
    """
    Получение ссылки на видео (m3u8)
    Публичный эндпоинт (не требует авторизации)
    """
    url = await get_video_m3u8(
        shikimori_id,
        episode_num,
        translation_id,
        quality
    )
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Видео недоступно"
        )
    
    return {
        "m3u8_url": url,
        "quality": quality,
        "episode": episode_num,
        "translation_id": translation_id
    }

# ═══════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ (ПОИСК)
# ═══════════════════════════════════════════

@app.get("/api/users/search", response_model=List[UserShort])
async def search_users(
    query: str,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Поиск пользователей по имени или username
    """
    if not query or len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Запрос должен содержать минимум 2 символа"
        )
    
    search_pattern = f"%{query.lower()}%"
    
    users = db.query(User).filter(
        (func.lower(User.name).like(search_pattern)) |
        (func.lower(User.username).like(search_pattern))
    ).filter(
        User.id != current_user.id  # Исключаем себя
    ).limit(limit).all()
    
    return users


@app.get("/api/users", response_model=List[UserShort])
async def get_all_users(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получить список всех пользователей
    """
    users = db.query(User).filter(
        User.id != current_user.id  # Исключаем себя
    ).offset(offset).limit(limit).all()
    
    return users

# ═══════════════════════════════════════════
# УВЕДОМЛЕНИЯ
# ═══════════════════════════════════════════

@app.get("/api/notifications", response_model=List[NotificationItem])
async def get_notifications(
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить уведомления пользователя"""
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(desc(Notification.created_at)).limit(limit).all()
    
    return notifications


@app.get("/api/notifications/unread/count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить количество непрочитанных уведомлений"""
    count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).scalar()
    
    return {"count": count or 0}


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Пометить уведомление как прочитанное"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(404, "Уведомление не найдено")
    
    notification.is_read = True
    db.commit()
    
    return {"success": True}


@app.put("/api/notifications/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Пометить все уведомления как прочитанные"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    return {"success": True}


# ═══════════════════════════════════════════
# ДРУЗЬЯ
# ═══════════════════════════════════════════

@app.get("/api/friends", response_model=List[FriendshipResponse])
async def get_friends(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список друзей (только accepted)"""
    sent_friendships = db.query(Friendship).filter(
        Friendship.user_id == current_user.id,
        Friendship.status == "accepted"
    ).all()
    
    received_friendships = db.query(Friendship).filter(
        Friendship.friend_id == current_user.id,
        Friendship.status == "accepted"
    ).all()
    
    result = []
    
    for fs in sent_friendships:
        result.append(FriendshipResponse(
            id=fs.id,
            status=fs.status,
            user=fs.user,
            friend=fs.friend,
            created_at=fs.created_at
        ))
    
    for fs in received_friendships:
        result.append(FriendshipResponse(
            id=fs.id,
            status=fs.status,
            user=fs.user,
            friend=fs.friend,
            created_at=fs.created_at
        ))
    
    return result


@app.get("/api/friends/requests", response_model=List[FriendshipResponse])
async def get_friend_requests(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить входящие заявки в друзья"""
    requests = db.query(Friendship).filter(
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending"
    ).all()
    
    return [
        FriendshipResponse(
            id=r.id,
            status=r.status,
            user=r.user,
            friend=r.friend,
            created_at=r.created_at
        )
        for r in requests
    ]


@app.post("/api/friends/add", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def add_friend(
    data: FriendshipCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отправить заявку в друзья"""
    if data.friend_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя добавить себя в друзья"
        )
    
    friend = db.query(User).filter(User.id == data.friend_id).first()
    if not friend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    existing = db.query(Friendship).filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == data.friend_id)) |
        ((Friendship.user_id == data.friend_id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if existing:
        if existing.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Уже в друзьях"
            )
        elif existing.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Заявка уже отправлена"
            )
    
    friendship = Friendship(
        user_id=current_user.id,
        friend_id=data.friend_id,
        status="pending"
    )
    
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    
    # ✅ Создаём уведомление в БД
    notification = Notification(
        user_id=data.friend_id,
        type="friend_request",
        title="Новая заявка в друзья",
        message=f"{current_user.name} хочет добавить вас в друзья",
        sender_id=current_user.id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url
    )
    db.add(notification)
    db.commit()
    
    # ✅ Отправляем WebSocket уведомление
    await send_friend_request_notification(
        receiver_id=data.friend_id,
        sender_name=current_user.name,
        sender_id=current_user.id
    )
    
    return FriendshipResponse(
        id=friendship.id,
        status=friendship.status,
        user=friendship.user,
        friend=friendship.friend,
        created_at=friendship.created_at
    )


@app.put("/api/friends/accept/{friendship_id}", response_model=FriendshipResponse)
async def accept_friend_request(
    friendship_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Принять заявку в друзья"""
    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending"
    ).first()
    
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    friendship.status = "accepted"
    friendship.updated_at = func.now()
    
    db.commit()
    db.refresh(friendship)
    
    # ✅ Создаём уведомление в БД
    notification = Notification(
        user_id=friendship.user_id,
        type="friend_accepted",
        title="Заявка принята",
        message=f"{current_user.name} принял вашу заявку в друзья",
        sender_id=current_user.id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url
    )
    db.add(notification)
    db.commit()
    
    # ✅ Отправляем WebSocket уведомление
    await send_friend_accepted_notification(
        receiver_id=friendship.user_id,
        accepter_name=current_user.name,
        accepter_id=current_user.id
    )
    
    return FriendshipResponse(
        id=friendship.id,
        status=friendship.status,
        user=friendship.user,
        friend=friendship.friend,
        created_at=friendship.created_at
    )


@app.put("/api/friends/reject/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reject_friend_request(
    friendship_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отклонить заявку в друзья"""
    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending"
    ).first()
    
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    # ✅ Создаём уведомление в БД
    notification = Notification(
        user_id=friendship.user_id,
        type="friend_rejected",
        title="Заявка отклонена",
        message=f"{current_user.name} отклонил вашу заявку в друзья",
        sender_id=current_user.id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url
    )
    db.add(notification)
    
    # ✅ Отправляем WebSocket уведомление
    await send_friend_rejected_notification(
        receiver_id=friendship.user_id,
        rejecter_name=current_user.name,
        rejecter_id=current_user.id
    )
    
    # Удаляем заявку
    db.delete(friendship)
    db.commit()


@app.delete("/api/friends/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friendship_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить из друзей"""
    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        ((Friendship.user_id == current_user.id) | (Friendship.friend_id == current_user.id))
    ).first()
    
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Дружба не найдена"
        )
    
    db.delete(friendship)
    db.commit()


@app.get("/api/friends/check/{user_id}")
async def check_friendship(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Проверить статус дружбы с пользователем"""
    friendship = db.query(Friendship).filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id)) |
        ((Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if not friendship:
        return {
            "is_friend": False,
            "status": None,
            "friendship_id": None,
            "is_sender": False
        }
    
    return {
        "is_friend": friendship.status == "accepted",
        "status": friendship.status,
        "friendship_id": friendship.id,
        "is_sender": friendship.user_id == current_user.id
    }

# ═══════════════════════════════════════════
# АВТОРИЗАЦИЯ - БЕЗОПАСНОСТЬ
# ═══════════════════════════════════════════

@app.put("/api/auth/change-username")
async def change_username(
    data: ChangeUsername,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Изменить логин пользователя
    """
    # Проверяем что новый username не занят
    existing_user = db.query(User).filter(
        User.username == data.new_username.lower(),
        User.id != current_user.id
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот логин уже занят"
        )
    
    # Обновляем username
    current_user.username = data.new_username.lower()
    db.commit()
    
    new_token = create_access_token(data={"sub": current_user.username})
    
    return {
        "message": "Логин успешно изменён",
        "new_username": current_user.username,
        "access_token": new_token,  
        "token_type": "bearer"
    }


@app.put("/api/auth/change-password")
async def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Изменить пароль пользователя
    """
    # Проверяем старый пароль
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный старый пароль"
        )
    
    # Проверяем что новый пароль не совпадает со старым
    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль должен отличаться от старого"
        )
    
    # Проверяем длину нового пароля
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен быть не менее 6 символов"
        )
    
    # Обновляем пароль
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    
    return {"message": "Пароль успешно изменён"}

# ═══════════════════════════════════════════
# ONLINE STATUS
# ═══════════════════════════════════════════

@app.get("/api/users/online")
async def get_online_users(
    current_user: User = Depends(get_current_active_user)
):
    """Получить список онлайн пользователей"""
    from websocket_manager import online_users
    
    return {
        "online_user_ids": list(online_users.keys()),
        "count": len(online_users)
    }


@app.get("/api/friends/online")
async def get_online_friends_list(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить список онлайн друзей"""
    from websocket_manager import get_online_friends
    
    # Получаем всех друзей
    sent_friendships = db.query(Friendship).filter(
        Friendship.user_id == current_user.id,
        Friendship.status == "accepted"
    ).all()
    
    received_friendships = db.query(Friendship).filter(
        Friendship.friend_id == current_user.id,
        Friendship.status == "accepted"
    ).all()
    
    friend_ids = []
    for fs in sent_friendships:
        friend_ids.append(fs.friend_id)
    for fs in received_friendships:
        friend_ids.append(fs.user_id)
    
    # Получаем онлайн друзей
    online_friend_ids = get_online_friends(friend_ids)
    
    return {
        "online_friend_ids": online_friend_ids,
        "total_friends": len(friend_ids),
        "online_count": len(online_friend_ids)
    }

@app.get("/api/users/{user_id}/can-message")
async def check_can_message(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Проверить, может ли текущий пользователь написать сообщение другому пользователю
    """
    can_send, reason = await can_send_message_to_user(current_user.id, user_id, db)
    
    return {
        "can_message": can_send,
        "reason": reason if not can_send else None
    }

@app.get("/api/users/{user_id}/online")
async def check_user_online(
    user_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Проверить онлайн ли пользователь"""
    from websocket_manager import is_user_online
    
    return {
        "user_id": user_id,
        "is_online": is_user_online(user_id)
    }

# ═══════════════════════════════════════════
# УВЕДОМЛЕНИЯ
# ═══════════════════════════════════════════

@app.get("/api/notifications/unread")
async def get_unread_notifications_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить количество непрочитанных уведомлений"""
    # Считаем входящие заявки
    pending_requests = db.query(func.count(Friendship.id)).filter(
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending"
    ).scalar()
    
    return {
        "count": pending_requests or 0
    }


@app.put("/api/friends/reject/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reject_friend_request(
    friendship_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отклонить заявку в друзья"""
    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending"
    ).first()
    
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка не найдена"
        )
    
    # ✅ Создаём уведомление отправителю (опционально)
    notification = Notification(
        user_id=friendship.user_id,
        type="friend_rejected",
        title="Заявка отклонена",
        message=f"{current_user.name} отклонил вашу заявку в друзья",
        sender_id=current_user.id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url
    )
    db.add(notification)
    
    # Удаляем заявку
    db.delete(friendship)
    db.commit()

@app.delete("/api/friends/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(
    friendship_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Удалить из друзей
    """
    friendship = db.query(Friendship).filter(
        Friendship.id == friendship_id,
        ((Friendship.user_id == current_user.id) | (Friendship.friend_id == current_user.id))
    ).first()
    
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Дружба не найдена"
        )
    
    db.delete(friendship)
    db.commit()


@app.get("/api/friends/check/{user_id}")
async def check_friendship(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Проверить статус дружбы с пользователем
    """
    friendship = db.query(Friendship).filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id)) |
        ((Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if not friendship:
        return {
            "is_friend": False,
            "status": None,
            "friendship_id": None,
            "is_sender": False
        }
    
    return {
        "is_friend": friendship.status == "accepted",
        "status": friendship.status,
        "friendship_id": friendship.id,
        "is_sender": friendship.user_id == current_user.id
    }

@app.get("/api/friends/status/{user_id}")
async def get_friendship_status(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получить статус дружбы с пользователем
    Возвращает: self, none, pending_sent, pending_received, friends
    """
    # Если это свой профиль
    if user_id == current_user.id:
        return {"status": "self"}
    
    # Ищем дружбу в обе стороны
    friendship = db.query(Friendship).filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id)) |
        ((Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    # Если дружбы нет
    if not friendship:
        return {"status": "none"}
    
    # Если дружба принята
    if friendship.status == "accepted":
        return {
            "status": "friends",
            "friendship_id": friendship.id
        }
    
    # Если заявка отправлена текущим пользователем
    if friendship.user_id == current_user.id and friendship.status == "pending":
        return {
            "status": "pending_sent",
            "friendship_id": friendship.id
        }
    
    # Если заявка получена текущим пользователем
    if friendship.friend_id == current_user.id and friendship.status == "pending":
        return {
            "status": "pending_received",
            "friendship_id": friendship.id
        }
    
    return {"status": "none"}

# ═══════════════════════════════════════════
# ЧАТЫ
# ═══════════════════════════════════════════

async def can_send_message_to_user(sender_id: int, receiver_id: int, db: Session) -> tuple[bool, str]:
    """
    Проверяет, может ли sender отправить сообщение receiver
    
    ✅ ВАЖНО: message_privacy контролирует КТО МОЖЕТ ПИСАТЬ МНЕ, а не кому я могу писать!
    
    Проверяем ТОЛЬКО настройки ПОЛУЧАТЕЛЯ!
    
    Returns:
        (bool, str): (Можно отправить?, Причина отказа)
    """
    
    # ════════════════════════════════════════════════════════════════
    # ПРОВЕРЯЕМ ТОЛЬКО ПОЛУЧАТЕЛЯ
    # ════════════════════════════════════════════════════════════════
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        return False, "Пользователь не найден"
    
    receiver_privacy = receiver.message_privacy or "all"
    
    # ✅ Если получатель запретил ВСЕМ писать
    if receiver_privacy == "nobody":
        return False, "Пользователь запретил получать сообщения"
    
    # ✅ Если получатель принимает ТОЛЬКО от друзей
    if receiver_privacy == "friends_only":
        friendship = db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == sender_id, Friendship.friend_id == receiver_id),
                and_(Friendship.user_id == receiver_id, Friendship.friend_id == sender_id)
            ),
            Friendship.status == "accepted"
        ).first()
        
        if not friendship:
            return False, "Пользователь принимает сообщения только от друзей"
    
    # ✅ Всё ок (receiver_privacy == "all" или это друзья)
    return True, ""

@app.get("/api/chats", response_model=List[ChatItem])
async def get_chats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получить список чатов (только НЕ удалённые)
    ✅ Последнее сообщение учитывает restored_at
    """
    participants = db.query(ChatParticipant).filter(
        ChatParticipant.user_id == current_user.id,
        ChatParticipant.deleted_at == None  # Только НЕ удалённые
    ).all()
    
    chat_items = []
    
    for participant in participants:
        chat = participant.chat
        
        other_participant = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat.id,
            ChatParticipant.user_id != current_user.id
        ).first()
        
        # ✅ Получаем последнее сообщение С УЧЁТОМ restored_at
        last_message_query = db.query(Message).filter(
            Message.chat_id == chat.id,
            Message.deleted_at == None
        )
        
        # Если чат был восстановлен - показываем только новые сообщения
        if participant.restored_at:
            last_message_query = last_message_query.filter(
                Message.created_at >= participant.restored_at
            )
        
        last_message = last_message_query.order_by(
            Message.created_at.desc()
        ).first()
        
        # ✅ Считаем непрочитанные С УЧЁТОМ restored_at
        unread_query = db.query(Message).filter(
            Message.chat_id == chat.id,
            Message.sender_id != current_user.id,
            Message.deleted_at == None
        )
        
        if participant.restored_at:
            unread_query = unread_query.filter(
                Message.created_at >= participant.restored_at
            )
        
        if participant.last_read_at:
            unread_count = unread_query.filter(
                Message.created_at > participant.last_read_at
            ).count()
        else:
            unread_count = unread_query.count()
        
        chat_item = {
            "id": chat.id,
            "type": chat.type,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "unread_count": unread_count
        }
        
        if other_participant:
            other_user = other_participant.user
            chat_item.update({
                "other_user_id": other_user.id,
                "other_user_name": other_user.name,
                "other_user_username": other_user.username,
                "other_user_avatar": other_user.avatar_url
            })
        
        if last_message:
            chat_item.update({
                "last_message": last_message.content,
                "last_message_time": last_message.created_at,
                "last_message_sender_id": last_message.sender_id
            })
        
        chat_items.append(ChatItem(**chat_item))
    
    chat_items.sort(key=lambda x: x.last_message_time or x.created_at, reverse=True)
    
    return chat_items


@app.post("/api/chats", response_model=ChatItem)
async def create_chat(
    data: ChatCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Создать чат с пользователем
    ✅ НЕ восстанавливает удалённые чаты
    ✅ Всегда создаёт НОВЫЙ чат
    """
    
    # ════════════════════════════════════════════════════════════════
    # ✅ ПРОВЕРКА ПРИВАТНОСТИ
    # ════════════════════════════════════════════════════════════════
    can_send, reason = await can_send_message_to_user(current_user.id, data.friend_id, db)
    if not can_send:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )
    
    # ════════════════════════════════════════════════════════════════
    # ✅ ИЩЕМ ТОЛЬКО НЕ УДАЛЁННЫЕ ЧАТЫ
    # ════════════════════════════════════════════════════════════════
    existing_participant = db.query(ChatParticipant).filter(
        ChatParticipant.user_id == current_user.id,
        ChatParticipant.deleted_at == None  # ✅ ТОЛЬКО НЕ УДАЛЁННЫЕ!
    ).all()
    
    for part in existing_participant:
        # Проверяем есть ли в этом чате второй участник
        other = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == part.chat_id,
            ChatParticipant.user_id == data.friend_id,
            ChatParticipant.deleted_at == None  # ✅ И У НЕГО ТОЖЕ НЕ УДАЛЁН!
        ).first()
        
        if other:
            # ✅ Чат уже существует и НЕ удалён
            print(f"✅ Чат {part.chat_id} уже существует")
            return await get_chat_item(part.chat_id, current_user.id, db)
    
    # ════════════════════════════════════════════════════════════════
    # ✅ ВСЕГДА СОЗДАЁМ НОВЫЙ ЧАТ (удалённые НЕ восстанавливаем)
    # ════════════════════════════════════════════════════════════════
    new_chat = Chat(type="private")
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    
    # Добавляем участников
    participant1 = ChatParticipant(chat_id=new_chat.id, user_id=current_user.id)
    participant2 = ChatParticipant(chat_id=new_chat.id, user_id=data.friend_id)
    
    db.add(participant1)
    db.add(participant2)
    db.commit()
    
    print(f"✅ Создан новый чат {new_chat.id}")
    return await get_chat_item(new_chat.id, current_user.id, db)


async def get_chat_item(chat_id: int, user_id: int, db: Session) -> ChatItem:
    """Вспомогательная функция для получения ChatItem"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    
    other_participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id != user_id
    ).first()
    
    current_participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == user_id
    ).first()
    
    # ✅ Получаем последнее сообщение С УЧЁТОМ restored_at
    last_message_query = db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.deleted_at == None
    )
    
    if current_participant and current_participant.restored_at:
        last_message_query = last_message_query.filter(
            Message.created_at >= current_participant.restored_at
        )
    
    last_message = last_message_query.order_by(
        Message.created_at.desc()
    ).first()
    
    # ✅ Считаем непрочитанные С УЧЁТОМ restored_at
    from sqlalchemy import func, desc
    
    unread_query = db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.sender_id != user_id,
        Message.deleted_at == None
    )
    
    if current_participant and current_participant.restored_at:
        unread_query = unread_query.filter(
            Message.created_at >= current_participant.restored_at
        )
    
    if current_participant and current_participant.last_read_at:
        unread_count = unread_query.filter(
            Message.created_at > current_participant.last_read_at
        ).count()
    else:
        unread_count = unread_query.count()
    
    chat_item = {
        "id": chat.id,
        "type": chat.type,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "unread_count": unread_count
    }
    
    if other_participant:
        other_user = other_participant.user
        chat_item.update({
            "other_user_id": other_user.id,
            "other_user_name": other_user.name,
            "other_user_username": other_user.username,
            "other_user_avatar": other_user.avatar_url
        })
    
    if last_message:
        chat_item.update({
            "last_message": last_message.content,
            "last_message_time": last_message.created_at,
            "last_message_sender_id": last_message.sender_id
        })
    
    return ChatItem(**chat_item)


# ═══════════════════════════════════════════
# СООБЩЕНИЯ
# ═══════════════════════════════════════════

@app.get("/api/chats/{chat_id}/messages", response_model=List[MessageItem])
async def get_messages(
    chat_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получить сообщения чата
    ✅ Показываем только сообщения ПОСЛЕ последнего восстановления
    """
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(403, "Вы не являетесь участником этого чата")
    
    query = db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.deleted_at == None  # Не показываем удалённые
    )
    
    # ✅ КЛЮЧЕВАЯ ЛОГИКА: Если чат был восстановлен - показываем только НОВЫЕ сообщения
    if participant.restored_at:
        query = query.filter(Message.created_at >= participant.restored_at)
        print(f"📅 Показываем сообщения после {participant.restored_at}")
    
    if before_id:
        query = query.filter(Message.id < before_id)
    
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    messages.reverse()
    
    result = []
    for msg in messages:
        result.append(MessageItem(
            id=msg.id,
            chat_id=msg.chat_id,
            sender_id=msg.sender_id,
            sender_name=msg.sender.name,
            sender_avatar=msg.sender.avatar_url,
            content=msg.content,
            created_at=msg.created_at,
            is_edited=msg.is_edited,
            edited_at=msg.edited_at,
            is_read=msg.is_read
        ))
    
    return result

@app.post("/api/chats/{chat_id}/messages", response_model=MessageItem)
async def send_message(
    chat_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Отправить сообщение
    ✅ Автоматически восстанавливает чат с чистого листа
    ✅ НЕ проверяет приватность (чат уже существует)
    """
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(403, "Вы не являетесь участником этого чата")
    
    # ✅ ПОЛУЧАЕМ ID ПОЛУЧАТЕЛЯ
    other_participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id != current_user.id
    ).first()
    
    if not other_participant:
        raise HTTPException(404, "Получатель не найден")
    
    # ✅ НЕ ПРОВЕРЯЕМ приватность для существующих чатов!
    # Если чат уже существует - можно писать (как в Telegram/WhatsApp)
    # Проверка приватности работает только при СОЗДАНИИ чата
    
    # ✅ ВОССТАНАВЛИВАЕМ ЧАТ ДЛЯ ОБОИХ УЧАСТНИКОВ
    all_participants = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id
    ).all()
    
    current_time = datetime.utcnow()
    
    for p in all_participants:
        if p.deleted_at is not None:
            # ✅ Сохраняем МОМЕНТ ВОССТАНОВЛЕНИЯ
            # Все сообщения ДО этого момента останутся скрытыми
            p.restored_at = current_time
            p.deleted_at = None
            print(f"🔄 Чат {chat_id} восстановлен для {p.user_id} с момента {current_time}")
            print(f"   Старые сообщения ДО {current_time} будут скрыты")
    
    # Создаём новое сообщение
    new_message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=data.content,
        original_content=data.content
    )
    
    db.add(new_message)
    
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    chat.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(new_message)
    
    message_item = MessageItem(
        id=new_message.id,
        chat_id=new_message.chat_id,
        sender_id=new_message.sender_id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url,
        content=new_message.content,
        created_at=new_message.created_at,
        is_edited=new_message.is_edited,
        edited_at=new_message.edited_at,
        is_read=False
    )
    
    import asyncio
    from websocket_manager import send_message_to_chat
    
    ws_data = {
        'id': message_item.id,
        'chat_id': message_item.chat_id,
        'sender_id': message_item.sender_id,
        'sender_name': message_item.sender_name,
        'sender_avatar': message_item.sender_avatar,
        'content': message_item.content,
        'created_at': message_item.created_at.isoformat(),
        'is_edited': message_item.is_edited,
        'edited_at': message_item.edited_at.isoformat() if message_item.edited_at else None,
        'is_read': False
    }
    
    asyncio.create_task(send_message_to_chat(chat_id, current_user.id, ws_data))
    
    return message_item
    
@app.put("/api/chats/{chat_id}/read")
async def mark_chat_read(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Отметить все сообщения чата как прочитанные
    """
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником этого чата"
        )
    
    # Обновляем last_read_at
    participant.last_read_at = datetime.utcnow()
    
    db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.sender_id != current_user.id,
        Message.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    import asyncio
    from websocket_manager import send_read_receipt
    asyncio.create_task(send_read_receipt(chat_id, current_user.id))
    
    return {"message": "Сообщения отмечены как прочитанные"}

# ═══════════════════════════════════════════
# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ СООБЩЕНИЙ
# ═══════════════════════════════════════════

@app.put("/api/chats/{chat_id}/messages/{message_id}", response_model=MessageItem)
async def edit_message(
    chat_id: int,
    message_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Редактировать сообщение
    ✅ Сохраняем ВСЮ историю изменений в отдельной таблице
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.chat_id == chat_id
    ).first()
    
    if not message:
        raise HTTPException(404, "Сообщение не найдено")
    
    if message.sender_id != current_user.id:
        raise HTTPException(403, "Вы можете редактировать только свои сообщения")
    
    # Проверка 24 часов
    time_passed = datetime.utcnow() - message.created_at
    if time_passed > timedelta(hours=24):
        raise HTTPException(403, "Прошло больше 24 часов. Редактирование недоступно.")
    
    # ✅ Сохраняем старую версию в историю
    edit_record = MessageEditHistory(
        message_id=message.id,
        old_content=message.content,
        new_content=data.content,
        edited_by=current_user.id
    )
    db.add(edit_record)
    
    # ✅ Обновляем сообщение (original_content НЕ трогаем!)
    message.content = data.content  # Новый текст
    message.is_edited = True
    message.edited_at = datetime.utcnow()
    
    db.commit()
    db.refresh(message)
    
    message_item = MessageItem(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        sender_name=current_user.name,
        sender_avatar=current_user.avatar_url,
        content=message.content,
        created_at=message.created_at,
        is_edited=message.is_edited,
        edited_at=message.edited_at,
        is_read=message.is_read
    )
    
    # WebSocket
    import asyncio
    from websocket_manager import send_message_edited
    
    ws_data = {
        'id': message_item.id,
        'chat_id': message_item.chat_id,
        'sender_id': message_item.sender_id,
        'sender_name': message_item.sender_name,
        'sender_avatar': message_item.sender_avatar,
        'content': message_item.content,
        'created_at': message_item.created_at.isoformat(),
        'is_edited': message_item.is_edited,
        'edited_at': message_item.edited_at.isoformat() if message_item.edited_at else None,
        'is_read': message_item.is_read
    }
    
    asyncio.create_task(send_message_edited(chat_id, current_user.id, ws_data))
    
    return message_item


@app.delete("/api/chats/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    chat_id: int,
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    "Удалить" сообщение (на самом деле просто скрываем)
    ✅ Сообщение остаётся в БД для правоохранительных органов
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.chat_id == chat_id
    ).first()
    
    if not message:
        raise HTTPException(404, "Сообщение не найдено")
    
    if message.sender_id != current_user.id:
        raise HTTPException(403, "Вы можете удалять только свои сообщения")
    
    # Проверка 24 часов
    time_passed = datetime.utcnow() - message.created_at
    if time_passed > timedelta(hours=24):
        raise HTTPException(403, "Прошло больше 24 часов. Удаление недоступно.")
    
    # ✅ НЕ удаляем, только помечаем
    message.deleted_at = datetime.utcnow()
    message.deleted_by = current_user.id
    
    db.commit()
    
    print(f"👁️ Сообщение {message_id} скрыто (НЕ удалено из БД)")
    
    # WebSocket
    import asyncio
    from websocket_manager import send_message_deleted
    asyncio.create_task(send_message_deleted(chat_id, message_id, current_user.id))


@app.delete("/api/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Удалить чат для пользователя
    ✅ Помечаем как удалённый (данные остаются в БД)
    ✅ При восстановлении старые сообщения будут скрыты
    """
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user.id
    ).first()
    
    if not participant:
        raise HTTPException(403, "Вы не являетесь участником этого чата")
    
    # ✅ Помечаем как удалённый
    participant.deleted_at = datetime.utcnow()
    
    # ✅ restored_at НЕ трогаем - он сохраняется для следующего восстановления
    
    db.commit()
    
    print(f"🗑️ Чат {chat_id} удалён для пользователя {current_user.id}")
    print(f"   При восстановлении будут видны только новые сообщения")
# ═══════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════

from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Не найдено",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else str(exc),
            "status_code": 404
        }
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Ошибка сервера",
            "detail": str(exc),
            "status_code": 500
        }
    )


# Добавьте общий обработчик для всех HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:socket_app",  
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )