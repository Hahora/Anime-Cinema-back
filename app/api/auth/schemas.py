import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class UserRegister(BaseModel):
    model_config = {
        'from_attributes': True,
        'alias_generator': to_camel,
        'populate_by_name': True
    }

    username: str = Field(..., min_length=3, max_length=50, description="Логин")
    password: str = Field(..., min_length=8, description="Пароль")
    name: str = Field(..., min_length=2, max_length=100, description="Имя")
    admin_key: Optional[str] = Field(None, description="Админ ключ для регистрации")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Имя пользователя: только буквы, цифры, _, -')
        return v.lower()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль минимум 8 символов')
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', v):
            raise ValueError('Пароль: 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол')
        return v

    @model_validator(mode='after')
    def validate_admin_key(self):
        if self.admin_key is None:
            raise ValueError('Требуется admin_key для регистрации')
        return self


class Token(BaseModel):
    model_config = {'from_attributes': True}

    access_token: str
    token_type: str = "bearer"
