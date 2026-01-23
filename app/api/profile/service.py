from typing import Dict, Any

from sqlalchemy.orm import Session

from app.api.auth.utils import create_access_token, verify_password, get_password_hash
from app.api.profile.models import User
from app.api.profile.schemas import UserProfile, UserProfileUpdate, ChangeUsername, ChangePassword
from app.api.profile.utils import get_user_stats


class ProfileService:
    def __init__(self, db: Session):
        self.db = db

    def get_my_profile(self, current_user: User) -> UserProfile:
        stats = get_user_stats(self.db, current_user.id)
        return UserProfile(
            id=current_user.id,
            username=current_user.username,
            name=current_user.name,
            avatar_url=current_user.avatar_url,
            cover_url=current_user.cover_url,
            bio=current_user.bio,
            created_at=current_user.created_at,
            message_privacy=current_user.message_privacy or "all",
            **stats
        )

    def get_public_profile(self, user_id: int) -> UserProfile:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        stats = get_user_stats(self.db, user.id)
        return UserProfile(
            id=user.id,
            username=user.username,
            name=user.name,
            avatar_url=user.avatar_url,
            cover_url=user.cover_url,
            bio=user.bio,
            created_at=user.created_at,
            **stats
        )

    def update_profile(self, current_user: User, data: UserProfileUpdate) -> UserProfile:
        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(current_user, key, value)
        self.db.commit()
        self.db.refresh(current_user)
        return self.get_my_profile(current_user)

    def change_username(self, current_user: User, data: ChangeUsername) -> Dict[str, Any]:
        if self.db.query(User).filter(
                User.username == data.new_username.lower(),
                User.id != current_user.id
        ).first():
            raise ValueError("Имя пользователя уже занято")

        current_user.username = data.new_username.lower()
        self.db.commit()
        self.db.refresh(current_user)

        new_token = create_access_token({"sub": current_user.username})
        return {
            "message": "Имя пользователя изменено",
            "new_username": current_user.username,
            "access_token": new_token,
            "token_type": "bearer"
        }

    def change_password(self, current_user: User, data: ChangePassword) -> Dict[str, Any]:
        if not verify_password(data.current_password, current_user.hashed_password):
            raise ValueError("Неверный старый пароль")
        if verify_password(data.new_password, current_user.hashed_password):
            raise ValueError("Новый пароль совпадает со старым")
        if len(data.new_password) < 8:
            raise ValueError("Пароль слишком короткий")

        current_user.hashed_password = get_password_hash(data.new_password)
        self.db.commit()
        return {"message": "Пароль изменен"}

    def get_user(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def exists(self, user_id: int) -> bool:
        return self.get_user(user_id) is not None
