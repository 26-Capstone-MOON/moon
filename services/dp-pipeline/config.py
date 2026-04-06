from pathlib import Path

from pydantic_settings import BaseSettings


SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parent.parent


def _env_files() -> tuple[str, ...]:
    files = [
        SERVICE_DIR / ".env",
        REPO_ROOT / ".env",
    ]
    return tuple(str(path) for path in files if path.exists())


class Settings(BaseSettings):
    """Load API keys and service settings from .env file."""

    tmap_api_key: str = ""
    kakao_api_key: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""
    google_places_api_key: str = ""
    openweather_api_key: str = ""
    openai_api_key: str = ""

    model_config = {"env_file": _env_files(), "env_file_encoding": "utf-8"}


settings = Settings()
