from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.api.friends.models import Friendship
from app.api.notifications.models import Notification
from app.api.profile.models import User


class NotificationService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.user_id = current_user.id

    def get_notifications(self, limit: int):
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == self.user_id)
            .order_by(desc(Notification.created_at))
            .limit(limit)
            .all()
        )

    def get_unread_count(self):
        count = (
            self.db.query(func.count(Notification.id))
            .filter(Notification.user_id == self.user_id, Notification.is_read == False)
            .scalar()
        )
        return count or 0

    def get_unread_friendship_count(self):
        count = (
            self.db.query(func.count(Friendship.id)).filter(
                Friendship.friend_id == self.user_id,
                Friendship.status == "pending"
            ).scalar()
        )
        return count or 0

    def mark_read(self, notification_id: int):
        notification = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == self.user_id)
            .first()
        )
        if not notification:
            return False
        notification.is_read = True
        self.db.commit()
        return True

    def mark_all_read(self):
        self.db.query(Notification).filter(
            Notification.user_id == self.user_id, Notification.is_read == False
        ).update({"is_read": True})
        self.db.commit()
