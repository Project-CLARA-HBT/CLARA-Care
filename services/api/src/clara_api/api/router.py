from fastapi import APIRouter

from clara_api.api.v1.endpoints import (
    admin_rag,
    auth,
    careguard,
    chat,
    council,
    health,
    mobile,
    phr,
    research,
    scribe,
    search,
    system,
    workspace,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(mobile.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(phr.router, prefix="/phr", tags=["phr"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(careguard.router, prefix="/careguard", tags=["careguard"])
api_router.include_router(council.router, prefix="/council", tags=["council"])
api_router.include_router(scribe.router, prefix="/scribe", tags=["scribe"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(workspace.router, prefix="/workspace", tags=["workspace"])
api_router.include_router(admin_rag.router, prefix="/admin/rag", tags=["admin-rag"])
