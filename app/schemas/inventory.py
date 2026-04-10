from sqlmodel import SQLModel
from datetime import datetime
from typing import Optional, List
from app.models.inventory import CategoriaProducto, TipoMovimiento, TipoDestino
import math

# --- MOVIMIENTOS ---

class MovimientoCreate(SQLModel):
    fecha: Optional[datetime] = None
    producto_id: int
    cantidad: float
    tipo: TipoMovimiento
    periodo_id: int
    semana_id: Optional[int] = None
    destino_tipo: Optional[TipoDestino] = None
    ruta_nombre: Optional[str] = None
    nota_terceros: Optional[str] = None

class MovimientoUpdate(SQLModel):
    fecha: Optional[datetime] = None
    producto_id: Optional[int] = None
    cantidad: Optional[float] = None
    tipo: Optional[TipoMovimiento] = None
    periodo_id: Optional[int] = None
    semana_id: Optional[int] = None
    destino_tipo: Optional[TipoDestino] = None
    ruta_nombre: Optional[str] = None
    nota_terceros: Optional[str] = None

class MovimientoRead(MovimientoCreate):
    id: int
    fecha: datetime
    # Opcional: Agregar nombre del producto para evitar joins extras en frontend
    # producto_nombre: Optional[str] = None 

# --- NUEVO: SCHEMA DE PAGINACIÓN ---
# Esto es lo que devolveremos al frontend
class MovimientoPaginated(SQLModel):
    data: List[MovimientoRead]
    total: int
    page: int
    limit: int
    total_pages: int

# --- PERIODOS ---
class PeriodoCreate(SQLModel):
    nombre: str
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool = True

class PeriodoRead(PeriodoCreate):
    id: int

# --- SEMANAS ---
class SemanaCreate(SQLModel):
    numero: int
    fecha_inicio: datetime
    fecha_fin: datetime
    periodo_id: int

class SemanaRead(SemanaCreate):
    id: int

# --- PRODUCTOS ---
class ProductoCreate(SQLModel):
    nombre: str
    categoria: CategoriaProducto
    descripcion: Optional[str] = None

class ProductoRead(ProductoCreate):
    id: int

# --- RUTAS ---
class RutaCreate(SQLModel):
    nombre: str
    descripcion: Optional[str] = None

class RutaRead(RutaCreate):
    id: int
    activa: bool
    
class StockItem(SQLModel):
    producto_id: int
    nombre: str
    categoria: str
    total_entradas: float
    total_salidas: float
    stock_actual: float
    total_terceros: float = 0