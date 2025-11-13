from pydantic.v1 import BaseSettings
from pydantic import Field



class Settings(BaseSettings):
    app_name: str = Field(default="pokedex-api")
    app_version: str = Field(default="1.0.0")

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    database_url: str = Field(default="sqlite:///./pokedex.db")

    class Config:
        env_file = ".env"


settings = Settings()
