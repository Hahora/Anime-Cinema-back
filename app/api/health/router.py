@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Anime Cinema API",
        "version": "3.0.0",
        "database": "PostgreSQL",
        "features": ["auth", "profiles", "favorites", "history", "websocket"]
    }


@app.get("/api/debug/privacy/{user_id}")
async def debug_privacy(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    return {
        "username": user.username,
        "message_privacy": user.message_privacy,
        "is_null": user.message_privacy is None,
        "effective": user.message_privacy or "all"
    }


@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    """Проверка работоспособности"""
    try:
        db.connection()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/api/websocket/stats")
async def websocket_stats(current_user: User = Depends(get_current_active_user)):
    """Статистика WebSocket подключений"""
    return get_connection_stats()
