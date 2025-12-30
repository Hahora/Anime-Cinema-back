from database import engine
from models import Message

# Удаляем старую таблицу
Message.__table__.drop(bind=engine, checkfirst=True)
print("🗑️  Таблица messages удалена!")

# Создаём новую с is_read
Message.__table__.create(bind=engine, checkfirst=True)
print("✅ Таблица messages создана с полем is_read!")

print("\n🎉 Таблица messages обновлена!")