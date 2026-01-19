from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from datetime import datetime

# --- ENUMS (Opciones fijas) ---
class CategoriaProducto(str, Enum):
    GRANO = "grano"
    GALERIA = "galeria"

class TipoMovimiento(str, Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"

class TipoDestino(str, Enum):
    RUTA = "ruta"
    TERCERO = "tercero"

# --- TABLAS (MODELOS) ---

class Periodo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str  # Ej: "Enero 2026"
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool = True
    
    # Relaciones (Laravel: hasMany)
    semanas: list["Semana"] = Relationship(back_populates="periodo")

class Semana(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    numero: int
    fecha_inicio: datetime
    fecha_fin: datetime
    
    # Claves foráneas (Laravel: belongsTo)
    periodo_id: int = Field(foreign_key="periodo.id")
    periodo: Periodo = Relationship(back_populates="semanas")

class Producto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    categoria: CategoriaProducto # GRANO o GALERIA
    descripcion: Optional[str] = None

class Movimiento(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha: datetime = Field(default_factory=datetime.utcnow)
    cantidad: float
    tipo: TipoMovimiento # ENTRADA o SALIDA
    
    # Relaciones Clave
    producto_id: int = Field(foreign_key="producto.id")
    
    # Contexto Temporal
    periodo_id: int = Field(foreign_key="periodo.id")
    semana_id: Optional[int] = Field(default=None, foreign_key="semana.id") # Nullable
    
    # Contexto de Salida (Rutas / Terceros)
    destino_tipo: Optional[TipoDestino] = None
    ruta_nombre: Optional[str] = None
    nota_terceros: Optional[str] = None
    
class Ruta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True, unique=True) # Ej: "Ruta Norte"
    descripcion: Optional[str] = None
    activa: bool = True