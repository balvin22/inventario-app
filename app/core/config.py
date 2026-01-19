from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventario API"
    VERSION: str = "1.0.0"
    
    # Por defecto usamos SQLite para pruebas locales.
    # Cuando vayamos a producción (Render), esto se leerá automáticamente de las variables de entorno.
    DATABASE_URL: str = "sqlite:///database.db"

    class Config:
        # Esto le dice a Pydantic que busque un archivo .env (estilo Laravel)
        env_file = ".env"
        case_sensitive = True

settings = Settings()