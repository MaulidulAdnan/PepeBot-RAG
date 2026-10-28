from fastapi import APIRouter, Depends

from app.api.endpoints import chat, document
from app.core.security import verify_internal_key

api_router = APIRouter(dependencies=[Depends(verify_internal_key)])
api_router.include_router(chat.router)
api_router.include_router(document.router)