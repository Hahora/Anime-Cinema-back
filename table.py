from database import engine
from models import Notification

# Создаём таблицу
Notification.__table__.create(bind=engine, checkfirst=True)
print("✅ Таблица notifications создана!")