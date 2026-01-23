import json
import logging

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.anime import router as anime_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.favorites import router as favorites_router
from app.api.friends import router as friends_router
from app.api.notifications import router as notifications_router
from app.api.profile import router as profile_router
from app.api.users import router as users_router
from app.api.watch_progress import router as watch_progress_router
from app.core.config import settings
from app.websocket.websocket_manager import sio

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API для Anime Cinema",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="../static"), name="static")

app.include_router(anime_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(favorites_router)
app.include_router(friends_router)
app.include_router(notifications_router)
app.include_router(profile_router)
app.include_router(users_router)
app.include_router(watch_progress_router)

socket_app = socketio.ASGIApp(sio, app)

openapi_schema = app.openapi()
with open("openapi.json", "w") as f:
    json.dump(openapi_schema, f, indent=2)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Не найдено",
            "path": str(request.url),
            "status_code": 404
        }
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    logger.error(f"Server error: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "error": "Ошибка сервера",
            "status_code": 500
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Внутренняя ошибка сервера",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        socket_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
