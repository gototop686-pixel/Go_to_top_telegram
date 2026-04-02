from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    manager_id: int
    groq_api_key: str
    work_start_hour: int = 9
    work_end_hour: int = 19
    database_url: str = "sqlite+aiosqlite:///bot_database.db"

    @property
    def async_database_url(self) -> str:
        # If it's a typical postgres:// url (from Render/Supabase), 
        # SQLAlchemy async engine requires postgresql+asyncpg://
        url = self.database_url.strip() # Remove any accidental newlines/spaces
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()
