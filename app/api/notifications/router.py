from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth.dependencies import get_current_active_user
from app.api.notifications.schemas import NotificationItem
from app.api.notifications.service import NotificationService
from app.api.profile.models import User
from app.database.database import get_db

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationItem])
async def get_notifications(
        limit: int = 20,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    service = NotificationService(db, current_user)
    return service.get_notifications(limit)


@router.get("/unread-count")
async def get_unread_count(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    service = NotificationService(db, current_user)
    return {"count": service.get_unread_count()}


@router.get("/unread-friends-count")
async def get_unread_notifications_count(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    service = NotificationService(db, current_user)
    return {"count": service.get_unread_friendship_count()}


@router.put("/read-all")
async def mark_all_read(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    service = NotificationService(db, current_user)
    service.mark_all_read()
    return {"success": True}


@router.put("/{notification_id}/read")
async def mark_notification_read(
        notification_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    service = NotificationService(db, current_user)
    success = service.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}
