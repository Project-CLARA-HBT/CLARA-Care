from fastapi import APIRouter

from clara_api.api.v1.endpoints import auth, careguard, chat, health, research, scribe, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(careguard.router, prefix="/careguard", tags=["careguard"])
api_router.include_router(scribe.router, prefix="/scribe", tags=["scribe"])
