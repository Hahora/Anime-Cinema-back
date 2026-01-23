import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

from fastapi import HTTPException, status
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.api.chats.models import ChatParticipant, Message, Chat, MessageEditHistory
from app.api.chats.schemas import ChatItem, ChatCreate, MessageItem, MessageCreate
from app.api.friends.models import Friendship
from app.api.profile.models import User
from app.websocket.websocket_manager import send_message_to_chat, send_read_receipt, send_message_deleted, \
    send_message_edited


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    async def get_chats(self, user_id: int) -> List[ChatItem]:
        participants = self.db.query(ChatParticipant).filter(
            ChatParticipant.user_id == user_id,
            ChatParticipant.deleted_at.is_(None)
        ).all()

        chat_items = []
        for participant in participants:
            chat = participant.chat
            other_participant = self.db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat.id,
                ChatParticipant.user_id != user_id
            ).first()

            # Последнее сообщение после restored_at
            last_message_query = self.db.query(Message).filter(
                Message.chat_id == chat.id,
                Message.deleted_at.is_(None)
            )
            if participant.restored_at:
                last_message_query = last_message_query.filter(
                    Message.created_at >= participant.restored_at
                )
            last_message = last_message_query.order_by(Message.created_at.desc()).first()

            # Непрочитанные сообщения
            unread_query = self.db.query(Message).filter(
                Message.chat_id == chat.id,
                Message.sender_id != user_id,
                Message.deleted_at.is_(None)
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

            chat_item_data = {
                "id": chat.id,
                "type": chat.type,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "unread_count": unread_count
            }

            if other_participant:
                other_user = other_participant.user
                chat_item_data.update({
                    "other_user_id": other_user.id,
                    "other_user_name": other_user.name,
                    "other_user_username": other_user.username,
                    "other_user_avatar": other_user.avatar_url
                })

            if last_message:
                chat_item_data.update({
                    "last_message": last_message.content,
                    "last_message_time": last_message.created_at,
                    "last_message_sender_id": last_message.sender_id
                })

            chat_items.append(ChatItem(**chat_item_data))

        chat_items.sort(key=lambda x: x.last_message_time or x.created_at, reverse=True)
        return chat_items

    async def create_chat(self, data: ChatCreate, user_id: int) -> ChatItem:
        can_send, reason = await self.can_send_message_to_user(user_id, data.friend_id)
        if not can_send:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

        # Поиск существующего чата
        existing_participants = self.db.query(ChatParticipant).filter(
            ChatParticipant.user_id == user_id,
            ChatParticipant.deleted_at.is_(None)
        ).all()

        for part in existing_participants:
            other = self.db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == part.chat_id,
                ChatParticipant.user_id == data.friend_id,
                ChatParticipant.deleted_at.is_(None)
            ).first()
            if other:
                return await self._get_chat_item(part.chat_id, user_id)

        # Создание нового чата
        new_chat = Chat(type="private")
        self.db.add(new_chat)
        self.db.commit()
        self.db.refresh(new_chat)

        participant1 = ChatParticipant(chat_id=new_chat.id, user_id=user_id)
        participant2 = ChatParticipant(chat_id=new_chat.id, user_id=data.friend_id)
        self.db.add(participant1)
        self.db.add(participant2)
        self.db.commit()

        return await self._get_chat_item(new_chat.id, user_id)

    async def get_messages(
            self,
            chat_id: int,
            user_id: int,
            limit: int = 50,
            before_id: Optional[int] = None
    ) -> List[MessageItem]:
        participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id
        ).first()
        if not participant:
            raise HTTPException(status_code=403, detail="Not participant")

        query = self.db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.deleted_at.is_(None)
        )
        if participant.restored_at:
            query = query.filter(Message.created_at >= participant.restored_at)
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

    async def send_message(
            self,
            chat_id: int,
            data: MessageCreate,
            current_user: User
    ) -> MessageItem:
        participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == current_user.id
        ).first()
        if not participant:
            raise HTTPException(status_code=403, detail="Not participant")

        other_participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id != current_user.id
        ).first()
        if not other_participant:
            raise HTTPException(status_code=404, detail="Chat not found")

        all_participants = self.db.query(ChatParticipant).filter(ChatParticipant.chat_id == chat_id).all()
        current_time = datetime.utcnow()
        for p in all_participants:
            if p.deleted_at is not None:
                p.restored_at = current_time
                p.deleted_at = None

        # Create message
        new_message = Message(
            chat_id=chat_id,
            sender_id=current_user.id,
            content=data.content,
            original_content=data.content
        )
        self.db.add(new_message)

        chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
        chat.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(new_message)

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

        # WebSocket
        ws_data = {
            "id": message_item.id,
            "chat_id": message_item.chat_id,
            "sender_id": message_item.sender_id,
            "sender_name": message_item.sender_name,
            "sender_avatar": message_item.sender_avatar,
            "content": message_item.content,
            "created_at": message_item.created_at.isoformat(),
            "is_edited": message_item.is_edited,
            "edited_at": message_item.edited_at.isoformat() if message_item.edited_at else None,
            "is_read": False
        }
        asyncio.create_task(send_message_to_chat(chat_id, current_user.id, ws_data))

        return message_item

    async def mark_chat_read(self, chat_id: int, user_id: int):
        participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id
        ).first()
        if not participant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not participant")

        participant.last_read_at = datetime.utcnow()
        self.db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.sender_id != user_id,
            Message.is_read == False
        ).update({"is_read": True})
        self.db.commit()

        asyncio.create_task(send_read_receipt(chat_id, user_id))
        return {"last_read_at": participant.last_read_at}

    async def edit_message(
            self,
            chat_id: int,
            message_id: int,
            data: MessageCreate,
            user_id: int
    ) -> MessageItem:
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.chat_id == chat_id
        ).first()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        if message.sender_id != user_id:
            raise HTTPException(status_code=403, detail="Not message owner")

        time_passed = datetime.utcnow() - message.created_at
        if time_passed > timedelta(hours=24):
            raise HTTPException(status_code=403, detail="24 hours passed")

        # Edit history
        edit_record = MessageEditHistory(
            message_id=message.id,
            old_content=message.content,
            new_content=data.content,
            edited_by=user_id
        )
        self.db.add(edit_record)

        message.content = data.content
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(message)

        message_item = MessageItem(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            sender_name=message.sender.name,
            sender_avatar=message.sender.avatar_url,
            content=message.content,
            created_at=message.created_at,
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            is_read=message.is_read
        )

        # WebSocket
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
        asyncio.create_task(send_message_edited(chat_id, user_id, ws_data))

        return message_item

    async def delete_message(self, chat_id: int, message_id: int, user_id: int):
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.chat_id == chat_id
        ).first()
        if not message:
            raise HTTPException(status_code=404)
        if message.sender_id != user_id:
            raise HTTPException(status_code=403)

        time_passed = datetime.utcnow() - message.created_at
        if time_passed > timedelta(hours=24):
            raise HTTPException(status_code=403, detail="24 hours passed")

        message.deleted_at = datetime.utcnow()
        message.deleted_by = user_id
        self.db.commit()

        asyncio.create_task(send_message_deleted(chat_id, message_id, user_id))

    async def delete_chat(self, chat_id: int, user_id: int):
        participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id
        ).first()
        if not participant:
            raise HTTPException(status_code=403)

        participant.deleted_at = datetime.utcnow()
        self.db.commit()

    async def can_send_message_to_user(
            self,
            sender_id: int,
            receiver_id: int
    ) -> Tuple[bool, str]:
        receiver = self.db.query(User).filter(User.id == receiver_id).first()
        if not receiver:
            return False, "User not found"

        receiver_privacy = receiver.message_privacy or "all"
        if receiver_privacy == "nobody":
            return False, "Privacy: nobody"
        if receiver_privacy == "friends_only":
            friendship = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == sender_id, Friendship.friend_id == receiver_id),
                    and_(Friendship.user_id == receiver_id, Friendship.friend_id == sender_id)
                ),
                Friendship.status == "accepted"
            ).first()
            if not friendship:
                return False, "Must be friends"
        return True, ""

    async def _get_chat_item(self, chat_id: int, user_id: int) -> ChatItem:
        chat = self.db.query(Chat).filter(Chat.id == chat_id).first()

        other_participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id != user_id
        ).first()

        current_participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id
        ).first()

        # ✅ Получаем последнее сообщение С УЧЁТОМ restored_at
        last_message_query = self.db.query(Message).filter(
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

        unread_query = self.db.query(Message).filter(
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
