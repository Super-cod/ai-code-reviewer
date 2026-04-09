import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI: str = os.getenv(
        "GITHUB_REDIRECT_URI",
        "http://localhost:8000/auth/github/callback",
    )
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./data/ai_code_reviewer.db",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-a-long-random-string")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    ANALYSIS_WORKDIR: str = os.getenv("ANALYSIS_WORKDIR", "./data/repos")
    MAX_INDEX_FILES: int = int(os.getenv("MAX_INDEX_FILES", "150"))
    MAX_INDEX_FILE_BYTES: int = int(os.getenv("MAX_INDEX_FILE_BYTES", "200000"))
    USE_VECTOR_INDEX: bool = _as_bool(os.getenv("USE_VECTOR_INDEX", "false"), default=False)

config = Config()
