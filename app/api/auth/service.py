from typing import Optional

from sqlalchemy.orm import Session

from app.api.auth.schemas import UserRegister
from app.api.auth.utils import get_password_hash, create_access_token, verify_password
from app.api.profile.models import User


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_data: UserRegister) -> str:
        if self._user_exists(user_data.username):
            raise ValueError("Пользователь с таким именем уже существует")

        user = User(
            username=user_data.username.lower(),
            name=user_data.name,
            hashed_password=get_password_hash(user_data.password)
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return create_access_token({"sub": user.username})

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        user = self._get_user_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            return None

        if not getattr(user, 'is_active', True):
            raise ValueError("Аккаунт деактивирован")

        return create_access_token({"sub": user.username})

    def _user_exists(self, username: str) -> bool:
        return self.db.query(User).filter(User.username == username).first() is not None

    def _get_user_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()
