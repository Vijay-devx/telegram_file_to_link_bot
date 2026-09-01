from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    api_id: int
    api_hash: str
    bot_token: str
    base_url: str = "http://localhost:8000"
    domain: str | None = None
    db_path: str = "sqlite.db"
    link_ttl_hours: int = 3
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
