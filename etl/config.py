"""ETL 설정 — 환경변수 로딩."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assembly_api_key: str = ""
    nec_api_key: str = ""
    data_go_kr_api_key: str = ""
    # AI 요약(좋은점/문제점) — Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    database_url: str = "postgresql+psycopg://pyosim:pyosim@localhost:5432/pyosim"


settings = Settings()
