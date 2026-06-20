"""ETL 설정 — 환경변수 로딩."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assembly_api_key: str = ""
    nec_api_key: str = ""
    data_go_kr_api_key: str = ""
    ofd_api_key: str = ""  # 열린재정 openapi.openfiscaldata.go.kr
    # AI 요약(좋은점/문제점) provider — "ollama"(로컬·무료·무제한) | "gemini"
    summary_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    @property
    def summary_model(self) -> str:
        return self.gemini_model if self.summary_provider == "gemini" else self.ollama_model
    database_url: str = "postgresql+psycopg://pyosim:pyosim@localhost:5432/pyosim"


settings = Settings()
