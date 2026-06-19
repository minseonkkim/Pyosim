"""앱 설정 — 환경변수 로딩."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pyosim:pyosim@localhost:5432/pyosim"
    cors_origins: str = "http://localhost:3000"
    env: str = "local"

    # 어드민 검토(Phase 2-3) — 빈 값이면 어드민 API 비활성(전부 401).
    admin_token: str = ""

    # LLM 문항 초안 생성(Phase 2-3) — 키 없으면 generate 엔드포인트만 비활성.
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
