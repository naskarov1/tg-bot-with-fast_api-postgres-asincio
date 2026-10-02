from pydantic_settings import BaseSettings, SettingsConfigDict
env_file=r"C:\Users\naska\PycharmProjects\pet_project_tg_bot\.env",

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=env_file,
        env_file_encoding="utf-8"
    )


settings = Settings()