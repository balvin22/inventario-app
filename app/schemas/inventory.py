from sqlmodel import SQLModel
from datetime import datetime
from typing import Optional
from app.models.inventory import CategoriaProducto, TipoMovimiento, TipoDestino

# --- MOVIMIENTOS ---
class MovimientoCreate(SQLModel):
    producto_id: int
    cantidad: float
    tipo: TipoMovimiento      # "entrada" o "salida"
    periodo_id: int
    semana_id: Optional[int] = None # Opcional (depende si es Grano o Galeria)
    
    # Solo para Salidas
    destino_tipo: Optional[TipoDestino] = None # "ruta" o "tercero"
    ruta_nombre: Optional[str] = None
    nota_terceros: Optional[str] = None

class MovimientoRead(MovimientoCreate):
    id: int
    fecha: datetime
    # Aquí podríamos agregar nombre_producto si quisiéramos devolverlo formateado

# --- PERIODOS ---
# Lo que el usuario envía para CREAR un periodo
class PeriodoCreate(SQLModel):
    nombre: str
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool = True

# Lo que la API responde (incluye el ID)
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

class RutaCreate(SQLModel):
    nombre: str
    descripcion: Optional[str] = None

class RutaRead(RutaCreate):
    id: int
    activa: bool    