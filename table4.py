from sqlalchemy import text
from database import engine

print("🔧 Добавляем message_privacy в users...\n")

with engine.begin() as conn:
    print("➕ Добавляем колонку message_privacy...")
    conn.execute(text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS message_privacy VARCHAR(20) DEFAULT 'all';
    """))

    print("📝 Добавляем комментарий...")
    conn.execute(text("""
        COMMENT ON COLUMN users.message_privacy
        IS 'Настройка приватности сообщений: all, friends_only, nobody';
    """))

    print("🔄 Обновляем существующих пользователей...")
    conn.execute(text("""
        UPDATE users
        SET message_privacy = 'all'
        WHERE message_privacy IS NULL;
    """))

    print("🔒 Проверяем и добавляем CHECK constraint...")
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'check_message_privacy'
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT check_message_privacy
                CHECK (message_privacy IN ('all', 'friends_only', 'nobody'));
            END IF;
        END$$;
    """))

print("\n🎉 Готово! message_privacy добавлено корректно")
