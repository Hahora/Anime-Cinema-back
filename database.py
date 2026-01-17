from sqlalchemy import create_engine, text  # ДОБАВИЛИ text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не найден в .env файле!")

# Создаём "движок" - подключение к БД
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Проверяет соединение перед использованием
    echo=False,  # True - показывает SQL запросы (для дебага)
)

# Фабрика сессий - для работы с БД
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Базовый класс для всех моделей
Base = declarative_base()


def get_db():
    """
    Создаёт сессию БД для каждого запроса.
    После использования - закрывает её.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """
    Проверяет подключение к БД
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # ИСПРАВЛЕНО
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False
