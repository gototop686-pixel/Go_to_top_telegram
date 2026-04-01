from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    manager_id: int
    gemini_api_key: str
    # Render or Supabase provide this
    database_url: str = "sqlite+aiosqlite:///bot_database.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()
