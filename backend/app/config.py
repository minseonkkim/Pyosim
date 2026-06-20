"""앱 설정 — 환경변수 로딩."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pyosim:pyosim@localhost:5432/pyosim"
    cors_origins: str = "http://localhost:3000"
    env: str = "local"

    # AI 요약(좋은점/문제점) — Google Gemini. 키 없으면 요약 기능은 조용히 비활성.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
