import os
import re
from dotenv import load_dotenv
from pathlib import Path

_HERE = Path(__file__).resolve()
# Muat .env root dulu sebagai sumber DB_USERNAME/DB_PASSWORD/DB_DATABASE,
# lalu .env ai-service (menang) agar ${VAR:-default} terinterpolasi benar
# baik saat jalan native Windows maupun di dalam Docker.
load_dotenv(_HERE.parents[3] / ".env", override=False)
load_dotenv(_HERE.parents[2] / ".env", override=True)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value or "${" in value:
        value = _expand(value or "")
    if not value:
        raise RuntimeError(f"Environment variable {name} wajib diisi")
    return value


def _expand(value: str) -> str:
    # Dukung ${VAR}, $VAR, dan ${VAR:-default} (tidak didukung os.path.expandvars).
    def repl(m: re.Match) -> str:
        var, default = m.group(1), m.group(2)
        return os.getenv(var, default if default is not None else "")

    value = re.sub(r"\$\{([^}:]+)(?::-(.*?))?\}", repl, value)
    return os.path.expandvars(value)


DATABASE_URL = _require("DATABASE_URL")
GEMINI_API_KEY = _require("GEMINI_API_KEY")