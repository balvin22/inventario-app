from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventario API"
    VERSION: str = "1.0.0"
    
    # Usamos ./database.db para ser explícitos con la ruta local
    DATABASE_URL: str = "sqlite:///./database.db"

    # Configuración moderna para Pydantic v2
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore" # Ignora variables extra en el .env que no usemos
    )

    # --- AUTO-CORRECCIÓN DE URL ---
    # Esto detecta si la URL viene de Neon como 'postgres://' y la cambia a 'postgresql://'
    # Así te ahorras editarla manualmente en Render.
    @field_validator("DATABASE_URL", mode="before")
    def corregir_url_postgres(cls, v: str):
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

settings = Settings()