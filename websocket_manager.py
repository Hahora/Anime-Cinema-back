from typing import Dict, Set
import socketio
from datetime import datetime

# Создаём Socket.IO сервер
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    logger=True,
    engineio_logger=False
)

# Хранилище подключений: {user_id: set(session_ids)}
user_connections: Dict[int, Set[str]] = {}


# ═══════════════════════════════════════════
# СОБЫТИЯ ПОДКЛЮЧЕНИЯ
# ═══════════════════════════════════════════

@sio.event
async def connect(sid, environ, auth):
    """Подключение клиента"""
    print(f"🔌 Client connected: {sid}")
    
    # Проверяем авторизацию
    if not auth or 'user_id' not in auth:
        print(f"❌ Unauthorized connection attempt: {sid}")
        return False
    
    user_id = auth['user_id']
    
    # Добавляем в список подключений
    if user_id not in user_connections:
        user_connections[user_id] = set()
    user_connections[user_id].add(sid)
    
    print(f"✅ User {user_id} connected (session: {sid})")
    print(f"📊 Active connections for user {user_id}: {len(user_connections[user_id])}")
    
    # Отправляем приветствие
    await sio.emit('connected', {
        'message': 'Connected to notification server',
        'user_id': user_id,
        'timestamp': datetime.utcnow().isoformat()
    }, room=sid)


@sio.event
async def disconnect(sid):
    """Отключение клиента"""
    print(f"🔌 Client disconnected: {sid}")
    
    # Удаляем из всех списков
    for user_id, sessions in list(user_connections.items()):
        if sid in sessions:
            sessions.remove(sid)
            print(f"✅ Removed session {sid} from user {user_id}")
            
            # Удаляем пользователя если нет активных сессий
            if not sessions:
                del user_connections[user_id]
                print(f"📊 No active sessions for user {user_id}")


# ═══════════════════════════════════════════
# ОТПРАВКА УВЕДОМЛЕНИЙ
# ═══════════════════════════════════════════

async def send_notification_to_user(user_id: int, notification_data: dict):
    """
    Отправить уведомление конкретному пользователю
    """
    if user_id not in user_connections:
        print(f"⚠️ User {user_id} not connected")
        return False
    
    sessions = user_connections[user_id]
    print(f"📬 Sending notification to user {user_id} ({len(sessions)} sessions)")
    
    # Отправляем всем активным сессиям пользователя
    for session_id in sessions:
        try:
            await sio.emit('notification', notification_data, room=session_id)
            print(f"✅ Notification sent to session {session_id}")
        except Exception as e:
            print(f"❌ Failed to send to session {session_id}: {e}")
    
    return True


async def send_friend_request_notification(receiver_id: int, sender_data: dict, notification_id: int):
    """Уведомление о новой заявке в друзья"""
    await send_notification_to_user(receiver_id, {
        'id': notification_id,
        'type': 'friend_request',
        'title': 'Новая заявка в друзья',
        'message': f"{sender_data['name']} хочет добавить вас в друзья",
        'sender_id': sender_data['id'],
        'sender_name': sender_data['name'],
        'sender_avatar': sender_data['avatar_url'],
        'is_read': False,
        'created_at': datetime.utcnow().isoformat()
    })


async def send_friend_accepted_notification(receiver_id: int, accepter_data: dict, notification_id: int):
    """Уведомление о принятии заявки"""
    await send_notification_to_user(receiver_id, {
        'id': notification_id,
        'type': 'friend_accepted',
        'title': 'Заявка принята',
        'message': f"{accepter_data['name']} принял вашу заявку в друзья",
        'sender_id': accepter_data['id'],
        'sender_name': accepter_data['name'],
        'sender_avatar': accepter_data['avatar_url'],
        'is_read': False,
        'created_at': datetime.utcnow().isoformat()
    })


async def send_friend_rejected_notification(receiver_id: int, rejecter_data: dict, notification_id: int):
    """Уведомление об отклонении заявки"""
    await send_notification_to_user(receiver_id, {
        'id': notification_id,
        'type': 'friend_rejected',
        'title': 'Заявка отклонена',
        'message': f"{rejecter_data['name']} отклонил вашу заявку в друзья",
        'sender_id': rejecter_data['id'],
        'sender_name': rejecter_data['name'],
        'sender_avatar': rejecter_data['avatar_url'],
        'is_read': False,
        'created_at': datetime.utcnow().isoformat()
    })


# ═══════════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════════

def get_connected_users():
    """Получить список подключенных пользователей"""
    return list(user_connections.keys())


def get_user_sessions(user_id: int):
    """Получить количество активных сессий пользователя"""
    return len(user_connections.get(user_id, set()))