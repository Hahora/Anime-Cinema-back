from typing import List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.api.friends.models import Friendship
from app.api.friends.schemas import FriendshipResponse, FriendshipCreate
from app.api.notifications.models import Notification
from app.api.profile.models import User
from app.websocket.websocket_manager import (
    send_friend_request_notification,
    send_friend_accepted_notification,
    send_friend_rejected_notification,
    get_online_friends
)


class FriendshipService:
    def __init__(self, db: Session):
        self.db = db

    def get_friends(self, user_id: int) -> List[FriendshipResponse]:
        friendships = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.status == "accepted"),
                and_(Friendship.friend_id == user_id, Friendship.status == "accepted")
            )
        ).all()
        return [FriendshipResponse.model_validate(fs) for fs in friendships]

    def get_friend_requests(self, user_id: int) -> List[FriendshipResponse]:
        requests = self.db.query(Friendship).filter(
            Friendship.friend_id == user_id, Friendship.status == "pending"
        ).all()
        return [FriendshipResponse.model_validate(r) for r in requests]

    async def add_friend(self, data: FriendshipCreate, current_user: User) -> FriendshipResponse:
        if data.friend_id == current_user.id:
            raise HTTPException(400, detail="Нельзя добавить себя в друзья")
        friend = self.db.query(User).filter(User.id == data.friend_id).first()
        if not friend:
            raise HTTPException(404, detail="Пользователь не найден")
        existing = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == current_user.id, Friendship.friend_id == data.friend_id),
                and_(Friendship.user_id == data.friend_id, Friendship.friend_id == current_user.id)
            )
        ).first()
        if existing:
            if existing.status == "accepted":
                raise HTTPException(400, detail="Уже в друзьях")
            if existing.status == "pending":
                raise HTTPException(400, detail="Заявка уже отправлена")
        friendship = Friendship(user_id=current_user.id, friend_id=data.friend_id, status="pending")
        self.db.add(friendship)
        self.db.commit()
        self.db.refresh(friendship)
        # Уведомление
        notification = Notification(
            user_id=data.friend_id, type="friend_request",
            title="Новая заявка в друзья",
            message=f"{current_user.name} хочет добавить вас в друзья",
            sender_id=current_user.id, sender_name=current_user.name, sender_avatar=current_user.avatar_url
        )
        self.db.add(notification)
        self.db.commit()
        await send_friend_request_notification(receiver_id=data.friend_id, sender_name=current_user.name,
                                               sender_id=current_user.id)
        return FriendshipResponse.model_validate(friendship)

    async def accept_friend_request(self, friendship_id: int, current_user: User) -> FriendshipResponse:
        friendship = self.db.query(Friendship).filter(
            Friendship.id == friendship_id,
            Friendship.friend_id == current_user.id,
            Friendship.status == "pending"
        ).first()
        if not friendship:
            raise HTTPException(404, detail="Заявка не найдена")
        friendship.status = "accepted"
        friendship.updated_at = func.now()
        self.db.commit()
        self.db.refresh(friendship)
        notification = Notification(
            user_id=friendship.user_id, type="friend_accepted",
            title="Заявка принята",
            message=f"{current_user.name} принял вашу заявку в друзья",
            sender_id=current_user.id, sender_name=current_user.name, sender_avatar=current_user.avatar_url
        )
        self.db.add(notification)
        self.db.commit()
        await send_friend_accepted_notification(receiver_id=friendship.user_id, accepter_name=current_user.name,
                                                accepter_id=current_user.id)
        return FriendshipResponse.model_validate(friendship)

    def reject_friend_request(self, friendship_id: int, current_user: User):
        friendship = self.db.query(Friendship).filter(
            Friendship.id == friendship_id,
            Friendship.friend_id == current_user.id,
            Friendship.status == "pending"
        ).first()
        if not friendship:
            raise HTTPException(404, detail="Заявка не найдена")
        # Уведомление
        notification = Notification(
            user_id=friendship.user_id, type="friend_rejected",
            title="Заявка отклонена",
            message=f"{current_user.name} отклонил вашу заявку в друзья",
            sender_id=current_user.id, sender_name=current_user.name, sender_avatar=current_user.avatar_url
        )
        self.db.add(notification)
        self.db.delete(friendship)
        self.db.commit()
        send_friend_rejected_notification(receiver_id=friendship.user_id, rejecter_name=current_user.name,
                                          rejecter_id=current_user.id)

    def remove_friend(self, friendship_id: int, current_user_id: int):
        friendship = self.db.query(Friendship).filter(
            Friendship.id == friendship_id,
            or_(Friendship.user_id == current_user_id, Friendship.friend_id == current_user_id)
        ).first()
        if not friendship:
            raise HTTPException(404, detail="Дружба не найдена")
        self.db.delete(friendship)
        self.db.commit()

    def check_friendship(self, user_id: int, current_user_id: int) -> Dict[str, Any]:
        friendship = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == current_user_id, Friendship.friend_id == user_id),
                and_(Friendship.user_id == user_id, Friendship.friend_id == current_user_id)
            )
        ).first()
        if not friendship:
            return {"is_friend": False, "status": None, "friendship_id": None, "is_sender": False}
        return {
            "is_friend": friendship.status == "accepted",
            "status": friendship.status,
            "friendship_id": friendship.id,
            "is_sender": friendship.user_id == current_user_id
        }

    def get_friendship_status(self, user_id: int, current_user_id: int) -> Dict[str, Any]:
        if user_id == current_user_id:
            return {"status": "self"}
        friendship = self.db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == current_user_id, Friendship.friend_id == user_id),
                and_(Friendship.user_id == user_id, Friendship.friend_id == current_user_id)
            )
        ).first()
        if not friendship:
            return {"status": "none"}
        if friendship.status == "accepted":
            return {"status": "friends", "friendship_id": friendship.id}
        if friendship.user_id == current_user_id and friendship.status == "pending":
            return {"status": "pending_sent", "friendship_id": friendship.id}
        if friendship.friend_id == current_user_id and friendship.status == "pending":
            return {"status": "pending_received", "friendship_id": friendship.id}
        return {"status": "none"}

    def get_online_friends(self, current_user_id: int) -> Dict[str, Any]:
        sent = self.db.query(Friendship.user_id, Friendship.friend_id).filter(
            Friendship.user_id == current_user_id, Friendship.status == "accepted"
        ).all()
        received = self.db.query(Friendship.user_id, Friendship.friend_id).filter(
            Friendship.friend_id == current_user_id, Friendship.status == "accepted"
        ).all()
        friend_ids = [fs.friend_id for fs in sent] + [fs.user_id for fs in received]
        online_ids = get_online_friends(friend_ids)
        return {
            "online_friend_ids": online_ids,
            "total_friends": len(friend_ids),
            "online_count": len(online_ids)
        }
