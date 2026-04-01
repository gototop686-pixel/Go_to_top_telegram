from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    manager_id: int
    gemini_api_key: str
    database_url: str = "sqlite+aiosqlite:///bot_database.db"

    @property
    def async_database_url(self) -> str:
        # If it's a typical postgres:// url (from Render/Supabase), 
        # SQLAlchemy async engine requires postgresql+asyncpg://
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()
