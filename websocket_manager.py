import socketio
from typing import Dict, Set
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════
# SOCKETIO SERVER
# ═══════════════════════════════════════════
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:5173"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    logger=True,
    engineio_logger=True
)

# Хранение подключений: {user_id: set(session_ids)}
user_connections: Dict[int, Set[str]] = {}

# ═══════════════════════════════════════════
# СОБЫТИЯ ПОДКЛЮЧЕНИЯ
# ═══════════════════════════════════════════
@sio.event
async def connect(sid, environ, auth):
    """Подключение клиента"""
    print(f"🔌 Client connecting: {sid}")
    
    if not auth or 'user_id' not in auth:
        print(f"❌ Connection rejected: no user_id")
        return False
    
    user_id = auth['user_id']
    
    # Добавляем сессию к пользователю
    if user_id not in user_connections:
        user_connections[user_id] = set()
    user_connections[user_id].add(sid)
    
    print(f"✅ User {user_id} connected (session: {sid})")
    print(f"📊 Active connections: {len(user_connections)}")
    
    return True


@sio.event
async def disconnect(sid):
    """Отключение клиента"""
    print(f"🔌 Client disconnecting: {sid}")
    
    # Удаляем сессию из всех пользователей
    for user_id, sessions in list(user_connections.items()):
        if sid in sessions:
            sessions.remove(sid)
            print(f"👋 User {user_id} disconnected (session: {sid})")
            
            # Если у пользователя не осталось сессий, удаляем его
            if not sessions:
                del user_connections[user_id]
            break
    
    print(f"📊 Active connections: {len(user_connections)}")


# ═══════════════════════════════════════════
# ОТПРАВКА УВЕДОМЛЕНИЙ
# ═══════════════════════════════════════════
async def send_notification_to_user(user_id: int, notification_data: dict):
    """Отправить уведомление конкретному пользователю"""
    if user_id not in user_connections:
        print(f"⚠️ User {user_id} not connected, notification not sent")
        return
    
    sessions = user_connections[user_id]
    print(f"📤 Sending notification to user {user_id} ({len(sessions)} sessions)")
    
    for session_id in sessions:
        try:
            await sio.emit('notification', notification_data, room=session_id)
            print(f"✅ Notification sent to session {session_id}")
        except Exception as e:
            print(f"❌ Failed to send to session {session_id}: {e}")


async def send_friend_request_notification(receiver_id: int, sender_name: str, sender_id: int):
    """Уведомление о заявке в друзья"""
    await send_notification_to_user(receiver_id, {
        'type': 'friend_request',
        'message': f'{sender_name} отправил вам заявку в друзья',
        'sender_id': sender_id,
        'sender_name': sender_name,
    })


async def send_friend_accepted_notification(receiver_id: int, accepter_name: str, accepter_id: int):
    """Уведомление о принятии заявки"""
    await send_notification_to_user(receiver_id, {
        'type': 'friend_accepted',
        'message': f'{accepter_name} принял вашу заявку в друзья',
        'accepter_id': accepter_id,
        'accepter_name': accepter_name,
    })


async def send_friend_rejected_notification(receiver_id: int, rejecter_name: str, rejecter_id: int):
    """Уведомление об отклонении заявки"""
    await send_notification_to_user(receiver_id, {
        'type': 'friend_rejected',
        'message': f'{rejecter_name} отклонил вашу заявку в друзья',
        'rejecter_id': rejecter_id,
        'rejecter_name': rejecter_name,
    })


# ═══════════════════════════════════════════
# СТАТИСТИКА ПОДКЛЮЧЕНИЙ
# ═══════════════════════════════════════════
def get_connection_stats():
    """Получить статистику подключений"""
    return {
        'total_users': len(user_connections),
        'total_sessions': sum(len(sessions) for sessions in user_connections.values()),
        'users': {
            user_id: len(sessions)
            for user_id, sessions in user_connections.items()
        }
    }