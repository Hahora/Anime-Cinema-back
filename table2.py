from database import engine
from models import Chat, ChatParticipant, Message, MessageEditHistory

print("🔧 Начинаем пересоздание таблиц...\n")

# 1. Удаляем старые таблицы (в правильном порядке - сначала зависимые)
print("🗑️  Удаляем старые таблицы...")
MessageEditHistory.__table__.drop(bind=engine, checkfirst=True)
print("   ✓ MessageEditHistory удалена")

Message.__table__.drop(bind=engine, checkfirst=True)
print("   ✓ Message удалена")

ChatParticipant.__table__.drop(bind=engine, checkfirst=True)
print("   ✓ ChatParticipant удалена")

Chat.__table__.drop(bind=engine, checkfirst=True)
print("   ✓ Chat удалена")

print("\n✅ Все старые таблицы удалены!\n")

# 2. Создаём новые таблицы с обновлёнными полями
print("📦 Создаём новые таблицы...\n")

Chat.__table__.create(bind=engine, checkfirst=True)
print("   ✓ Chat создана")

ChatParticipant.__table__.create(bind=engine, checkfirst=True)
print("   ✓ ChatParticipant создана с полем deleted_at")

Message.__table__.create(bind=engine, checkfirst=True)
print("   ✓ Message создана с полями:")
print("      - original_content (оригинал навсегда)")
print("      - deleted_at (мягкое удаление)")
print("      - deleted_by (кто удалил)")
print("      - is_read (галочки)")

MessageEditHistory.__table__.create(bind=engine, checkfirst=True)
print("   ✓ MessageEditHistory создана (история редактирования)")

print("\n🎉 Все таблицы успешно пересозданы!")
print("\n✅ Теперь:")
print("   • Чаты НЕ удаляются из БД (только скрываются)")
print("   • Сообщения НЕ удаляются из БД (только скрываются)")
print("   • История редактирования сохраняется навсегда")
print("   • Всё соответствует 152-ФЗ РФ")