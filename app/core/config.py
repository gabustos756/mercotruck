import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Mercotruck Enterprise"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Google Maps Platform Configuration
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    
    # PostgreSQL Configuration
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "fgabrielbustos")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "mercotruck")
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        pwd = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}{pwd}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        pwd = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
        return f"postgresql+psycopg2://{self.POSTGRES_USER}{pwd}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Configurable Business Engine Parameters
    DATA_FOLDER: str = os.getenv("DATA_FOLDER", "docs")
    FLETE_MIN: float = float(os.getenv("FLETE_MIN", "500.0"))
    FLETE_MAX: float = float(os.getenv("FLETE_MAX", "8000.0"))
    DOCS_MIN: int = int(os.getenv("DOCS_MIN", "5"))
    RADIO_KM: float = float(os.getenv("RADIO_KM", "100.0"))
    DIAS_RECIENTE: int = int(os.getenv("DIAS_RECIENTE", "90"))

    DEFAULT_TRUCK_CAPACITY_KG: float = 28500.0
    DEFAULT_RADIO_EXACTO_KM: float = 50.0
    DEFAULT_RADIO_CERCANO_KM: float = 100.0
    
    # Secret Key
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-mercotruck-enterprise-key-2026")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
