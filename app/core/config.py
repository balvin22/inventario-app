from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventario API"
    VERSION: str = "1.0.0"
    
    # Esta línea es la clave: 
    # Busca la variable DATABASE_URL en el sistema (Render). 
    # Si no la encuentra, usa sqlite (Local).
    DATABASE_URL: str = "sqlite:///./database.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("DATABASE_URL", mode="before")
    def corregir_url_postgres(cls, v: str):
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

settings = Settings()