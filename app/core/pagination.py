# app/core/pagination.py
from typing import Generic, TypeVar, List
from math import ceil
from sqlmodel import SQLModel, select, func, Session
from fastapi import Query

# 1. Definimos una variable genérica "T"
T = TypeVar("T")

# 2. El Schema de Respuesta Genérico
class Page(SQLModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    limit: int
    total_pages: int

# 3. Dependencia para recibir los parámetros
class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Número de página"),
        # --- CORRECCIÓN AQUÍ: Cambiamos 100 por 2000 ---
        limit: int = Query(20, le=2000, description="Registros por página"),
    ):
        self.page = page
        self.limit = limit

# 4. La Función Mágica
def paginate(session: Session, query, params: PaginationParams) -> Page[T]:
    """
    Recibe una query SQLModel lista (con filtros aplicados), 
    calcula el total y devuelve la página cortada.
    """
    # A. Contar total de registros
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()

    # B. Calcular paginación
    total_pages = ceil(total_count / params.limit)
    offset = (params.page - 1) * params.limit

    # C. Ejecutar la query con el corte (slice)
    items = session.exec(query.offset(offset).limit(params.limit)).all()

    # D. Retornar estructura estandarizada
    return Page(
        data=items,
        total=total_count,
        page=params.page,
        limit=params.limit,
        total_pages=total_pages
    )