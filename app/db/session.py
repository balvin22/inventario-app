from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# 1. Obtenemos la URL desde nuestra configuración
connection_string = settings.DATABASE_URL

# 2. Argumentos especiales solo para SQLite (para que no falle con hilos)
connect_args = {}
if "sqlite" in connection_string:
    connect_args["check_same_thread"] = False

# 3. Creamos el motor de base de datos
engine = create_engine(
    connection_string, 
    echo=True, # Muestra el SQL en consola (útil para debug)
    connect_args=connect_args
)

def get_session():
    """Dependency para inyección de DB en las rutas"""
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    """Crea las tablas definidas en los modelos"""
    SQLModel.metadata.create_all(engine)