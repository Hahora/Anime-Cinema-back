from database import engine
from models import Chat, ChatParticipant, Message

# Создаём таблицы чатов и сообщений
Chat.__table__.create(bind=engine, checkfirst=True)
print("✅ Таблица chats создана!")

ChatParticipant.__table__.create(bind=engine, checkfirst=True)
print("✅ Таблица chat_participants создана!")

Message.__table__.create(bind=engine, checkfirst=True)
print("✅ Таблица messages создана!")

print("\n🎉 Все таблицы для чатов успешно созданы!")