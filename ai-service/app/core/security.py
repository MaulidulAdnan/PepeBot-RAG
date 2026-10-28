"""Autentikasi antar-service.

Laravel wajib mengirim header `X-Internal-Key` yang nilainya sama dengan
INTERNAL_API_KEY. Endpoint kesehatan (`/`) sengaja dibiarkan terbuka agar
monitoring tetap bisa mengecek status tanpa membawa rahasia.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_internal_key_header = APIKeyHeader(name="X-Internal-Key", auto_error=False)


def verify_internal_key(key: str | None = Security(_internal_key_header)) -> None:
    if not settings.INTERNAL_API_KEY or key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Internal-Key tidak valid",
        )
