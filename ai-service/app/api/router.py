"""Papan pembagi lorong Kos Pepe (Fase 5).

Mendaftarkan kamar chat (tanya warga) dan document (titip koper admin)
agar dibaca gerbang utama main.py.
"""

from fastapi import APIRouter

from app.api.endpoints import chat, document

router = APIRouter()
router.include_router(chat.router)
router.include_router(document.router)
