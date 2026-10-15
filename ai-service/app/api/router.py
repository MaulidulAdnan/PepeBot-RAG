from fastapi import APIRouter
from app.api.endpoints import chat, document

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(document.router)