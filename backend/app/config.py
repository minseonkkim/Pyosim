"""앱 설정 — 환경변수 로딩."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pyosim:pyosim@localhost:5432/pyosim"
    cors_origins: str = "http://localhost:3000"
    env: str = "local"

    # AI 요약(좋은점/문제점) provider — "ollama"(로컬·무료·무제한) | "gemini"
    summary_provider: str = "ollama"
    # 로컬 Ollama (provider=ollama). 먼저 `ollama pull <모델>` 필요.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    # Google Gemini (provider=gemini). 무료 티어는 일일 호출수 제한 작음.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    @property
    def summary_model(self) -> str:
        """현재 provider 의 모델명(요약 출처 기록·호출에 사용)."""
        return self.gemini_model if self.summary_provider == "gemini" else self.ollama_model

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
