from database import engine
from models import Chat, ChatParticipant, Message, MessageEditHistory

print("🔧 Пересоздание таблиц с полем restored_at...\n")

# Удаляем старые таблицы (в обратном порядке зависимостей)
print("🗑️  Удаляем старые таблицы...")
MessageEditHistory.__table__.drop(bind=engine, checkfirst=True)
Message.__table__.drop(bind=engine, checkfirst=True)
ChatParticipant.__table__.drop(bind=engine, checkfirst=True)
Chat.__table__.drop(bind=engine, checkfirst=True)
print("✅ Старые таблицы удалены!\n")

# Создаём новые таблицы
print("📦 Создаём новые таблицы...")
Chat.__table__.create(bind=engine, checkfirst=True)
ChatParticipant.__table__.create(bind=engine, checkfirst=True)
Message.__table__.create(bind=engine, checkfirst=True)
MessageEditHistory.__table__.create(bind=engine, checkfirst=True)

print("\n🎉 Таблицы пересозданы!")
print("\n✅ ChatParticipant теперь имеет:")
print("   • deleted_at - когда удалил чат")
print("   • restored_at - момент восстановления (скрывает старые сообщения)")
print("\n✅ Логика работает:")
print("   1. Удалил чат → старые сообщения скрываются")
print("   2. Кто-то пишет → чат восстанавливается")
print("   3. Видны только новые сообщения!")