from datetime import datetime
from typing import Dict, Set

import socketio
from dotenv import load_dotenv

from app.api.chats.models import ChatParticipant
from app.api.friends.models import Friendship

load_dotenv()

# ═══════════════════════════════════════════
# SOCKETIO SERVER
# ═══════════════════════════════════════════
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        "https://m2-live.store",
        "http://m2-live.store",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    logger=True,
    engineio_logger=True,
    allow_upgrades=True,
)

# Хранилище подключений: user_id -> set of session_ids
user_connections: Dict[int, Set[str]] = {}

# Хранилище онлайн статусов: user_id -> timestamp последней активности
online_users: Dict[int, float] = {}


# ═══════════════════════════════════════════
# SOCKET EVENTS
# ═══════════════════════════════════════════

@sio.event
async def connect(sid, environ, auth):
    """Подключение клиента"""
    try:
        user_id = auth.get('user_id') if auth else None

        if not user_id:
            print(f"⚠️ Отклонено подключение {sid}: user_id не указан")
            return False

        user_id = int(user_id)

        # Добавляем соединение
        if user_id not in user_connections:
            user_connections[user_id] = set()
        user_connections[user_id].add(sid)

        # Отмечаем пользователя онлайн
        import time
        online_users[user_id] = time.time()

        print(f"✅ Пользователь {user_id} подключён (session: {sid})")
        print(f"📊 Всего подключений: {sum(len(sessions) for sessions in user_connections.values())}")
        print(f"🟢 Онлайн пользователей: {len(online_users)}")

        # Уведомляем друзей что пользователь онлайн
        await broadcast_online_status(user_id, True)

        return True

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False


@sio.event
async def disconnect(sid):
    """Отключение клиента"""
    try:
        # Находим пользователя по session id
        user_id = None
        for uid, sessions in user_connections.items():
            if sid in sessions:
                user_id = uid
                sessions.remove(sid)

                # Если у пользователя не осталось подключений
                if not sessions:
                    del user_connections[uid]
                    # Удаляем из онлайна
                    if uid in online_users:
                        del online_users[uid]
                    # Уведомляем друзей что пользователь офлайн
                    await broadcast_online_status(uid, False)

                break

        if user_id:
            print(f"🔌 Пользователь {user_id} отключён (session: {sid})")
            print(f"📊 Осталось подключений: {sum(len(sessions) for sessions in user_connections.values())}")
            print(f"🟢 Онлайн пользователей: {len(online_users)}")
        else:
            print(f"⚠️ Отключение неизвестной сессии: {sid}")

    except Exception as e:
        print(f"❌ Ошибка отключения: {e}")


@sio.event
async def typing(sid, data):
    """Обработка события 'печатает'"""
    try:
        # Находим user_id по session id
        user_id = None
        for uid, sessions in user_connections.items():
            if sid in sessions:
                user_id = uid
                break

        if user_id and 'chat_id' in data:
            chat_id = data['chat_id']
            await send_typing_to_chat(chat_id, user_id)
            print(f"⌨️ User {user_id} is typing in chat {chat_id}")

    except Exception as e:
        print(f"❌ Ошибка обработки typing: {e}")


# ═══════════════════════════════════════════
# ONLINE STATUS
# ═══════════════════════════════════════════

async def broadcast_online_status(user_id: int, is_online: bool):
    """Уведомить друзей о смене онлайн статуса"""
    try:
        from app.database.database import SessionLocal
        from sqlalchemy import or_, and_

        db = SessionLocal()

        try:
            # Находим всех друзей пользователя
            friendships = db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == user_id, Friendship.status == "accepted"),
                    and_(Friendship.friend_id == user_id, Friendship.status == "accepted")
                )
            ).all()

            friend_ids = set()
            for fs in friendships:
                if fs.user_id == user_id:
                    friend_ids.add(fs.friend_id)
                else:
                    friend_ids.add(fs.user_id)

            # Отправляем уведомление каждому онлайн другу
            for friend_id in friend_ids:
                if friend_id in user_connections:
                    await send_to_user(friend_id, 'user_online_status', {
                        'user_id': user_id,
                        'is_online': is_online
                    })

            print(
                f"📡 Отправлен статус {'🟢 онлайн' if is_online else '⚪ офлайн'} для пользователя {user_id} ({len(friend_ids)} друзей)")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка broadcast_online_status: {e}")


def get_online_friends(friend_ids: list) -> list:
    """Получить список ID друзей которые онлайн"""
    return [fid for fid in friend_ids if fid in online_users]


def is_user_online(user_id: int) -> bool:
    """Проверить онлайн ли пользователь"""
    return user_id in online_users


def get_connection_stats():
    """Получить статистику подключений"""
    return {
        "total_connections": sum(len(sessions) for sessions in user_connections.values()),
        "unique_users": len(user_connections),
        "online_users": len(online_users),
        "connections_per_user": {
            user_id: len(sessions)
            for user_id, sessions in user_connections.items()
        }
    }


# ═══════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════

async def send_to_user(user_id: int, event: str, data: dict):
    """Отправить событие конкретному пользователю"""
    if user_id in user_connections:
        for session_id in user_connections[user_id]:
            try:
                await sio.emit(event, data, room=session_id)
            except Exception as e:
                print(f"❌ Ошибка отправки {event} пользователю {user_id}: {e}")


async def send_notification_to_user(user_id: int, notification_data: dict):
    """Отправить уведомление пользователю через WebSocket"""
    await send_to_user(user_id, 'notification', notification_data)


# ═══════════════════════════════════════════
# FRIEND NOTIFICATIONS
# ═══════════════════════════════════════════

async def send_friend_request_notification(receiver_id: int, sender_name: str, sender_id: int):
    """Отправить уведомление о заявке в друзья"""
    notification = {
        'type': 'friend_request',
        'title': 'Новая заявка в друзья',
        'message': f'{sender_name} хочет добавить вас в друзья',
        'sender_id': sender_id,
        'sender_name': sender_name,
    }
    await send_notification_to_user(receiver_id, notification)


async def send_friend_accepted_notification(receiver_id: int, accepter_name: str, accepter_id: int):
    """Отправить уведомление о принятии заявки"""
    notification = {
        'type': 'friend_accepted',
        'title': 'Заявка принята',
        'message': f'{accepter_name} принял вашу заявку в друзья',
        'sender_id': accepter_id,
        'sender_name': accepter_name,
    }
    await send_notification_to_user(receiver_id, notification)


async def send_friend_rejected_notification(receiver_id: int, rejecter_name: str, rejecter_id: int):
    """Отправить уведомление об отклонении заявки"""
    notification = {
        'type': 'friend_rejected',
        'title': 'Заявка отклонена',
        'message': f'{rejecter_name} отклонил вашу заявку в друзья',
        'sender_id': rejecter_id,
        'sender_name': rejecter_name,
    }
    await send_notification_to_user(receiver_id, notification)


# ═══════════════════════════════════════════
# CHAT MESSAGES
# ═══════════════════════════════════════════

async def send_message_to_chat(chat_id: int, sender_id: int, message_data: dict):
    """Отправить сообщение всем участникам чата через WebSocket"""
    try:
        from app.database.database import SessionLocal

        db = SessionLocal()

        try:
            # Получаем всех участников чата
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            # Отправляем сообщение каждому участнику (кроме отправителя)
            for participant in participants:
                if participant.user_id != sender_id and participant.user_id in user_connections:
                    await send_to_user(participant.user_id, 'new_message', message_data)

            print(f"💬 Message sent to chat {chat_id} from user {sender_id}")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка send_message_to_chat: {e}")


async def send_typing_to_chat(chat_id: int, user_id: int):
    """Отправить событие "печатает" участникам чата"""
    try:
        from app.database.database import SessionLocal

        db = SessionLocal()

        try:
            # Получаем всех участников чата
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            # Отправляем событие каждому участнику (кроме отправителя)
            for participant in participants:
                if participant.user_id != user_id and participant.user_id in user_connections:
                    await send_to_user(participant.user_id, 'user_typing', {
                        'chat_id': chat_id,
                        'user_id': user_id
                    })

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка send_typing_to_chat: {e}")


async def send_read_receipt(chat_id: int, reader_id: int):
    """Отправить уведомление о прочтении сообщений"""
    try:
        from app.database.database import SessionLocal

        print(f"\n📨 send_read_receipt вызвана:")
        print(f"   chat_id: {chat_id}")
        print(f"   reader_id: {reader_id}")

        db = SessionLocal()

        try:
            # Получаем всех участников чата
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            print(f"   Участников в чате: {len(participants)}")

            event_data = {
                'chat_id': chat_id,
                'user_id': reader_id,
                'read_at': datetime.now().isoformat()
            }

            sent_count = 0
            for participant in participants:
                print(f"   Участник: user_id={participant.user_id}, онлайн={participant.user_id in user_connections}")

                if participant.user_id in user_connections:
                    await send_to_user(participant.user_id, 'message_read', event_data)
                    sent_count += 1
                    print(f"   ✅ Отправлено пользователю {participant.user_id}")
                else:
                    print(f"   ⚠️ Пользователь {participant.user_id} не в сети")

            print(f"   📊 Всего отправлено: {sent_count}")
            print(f"✓✓ Read receipt обработан для чата {chat_id}\n")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка send_read_receipt: {e}")
        import traceback
        traceback.print_exc()


async def send_message_edited(chat_id: int, editor_id: int, message_data: dict):
    """Отправить уведомление о редактировании сообщения"""
    try:
        from app.database.database import SessionLocal

        print(f"\n✏️ send_message_edited вызвана:")
        print(f"   chat_id: {chat_id}")
        print(f"   editor_id: {editor_id}")
        print(f"   message_id: {message_data.get('id')}")

        db = SessionLocal()

        try:
            # Получаем всех участников чата
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            # Отправляем событие каждому участнику (включая редактора для синхронизации)
            sent_count = 0
            for participant in participants:
                if participant.user_id in user_connections:
                    await send_to_user(participant.user_id, 'message_edited', message_data)
                    sent_count += 1
                    print(f"   ✅ Отправлено пользователю {participant.user_id}")

            print(f"   📊 Всего отправлено: {sent_count}")
            print(f"✏️ Message edited notification sent\n")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка send_message_edited: {e}")
        import traceback
        traceback.print_exc()


async def send_message_deleted(chat_id: int, message_id: int, deleter_id: int):
    """Отправить уведомление об удалении сообщения"""
    try:
        from app.database.database import SessionLocal

        print(f"\n🗑️ send_message_deleted вызвана:")
        print(f"   chat_id: {chat_id}")
        print(f"   message_id: {message_id}")
        print(f"   deleter_id: {deleter_id}")

        db = SessionLocal()

        try:
            # Получаем всех участников чата
            participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id
            ).all()

            event_data = {
                'chat_id': chat_id,
                'message_id': message_id,
                'deleted_by': deleter_id
            }

            # Отправляем событие каждому участнику (включая удалившего для синхронизации)
            sent_count = 0
            for participant in participants:
                if participant.user_id in user_connections:
                    await send_to_user(participant.user_id, 'message_deleted', event_data)
                    sent_count += 1
                    print(f"   ✅ Отправлено пользователю {participant.user_id}")

            print(f"   📊 Всего отправлено: {sent_count}")
            print(f"🗑️ Message deleted notification sent\n")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка send_message_deleted: {e}")
        import traceback
        traceback.print_exc()
