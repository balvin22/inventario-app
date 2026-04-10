from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, desc, select, func
from app.db.session import get_session
from app.core.pagination import paginate, Page, PaginationParams
from app.models.inventory import Movimiento, Producto, CategoriaProducto, TipoMovimiento, TipoDestino
from app.schemas.inventory import MovimientoCreate, MovimientoRead, MovimientoUpdate, MovimientoPaginated
from typing import Optional
import math

router = APIRouter(prefix="/movimientos", tags=["Movimientos"])

@router.post("/", response_model=MovimientoRead)
def registrar_movimiento(movimiento: MovimientoCreate, session: Session = Depends(get_session)):
    producto = session.get(Producto, movimiento.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # --- VALIDACIONES DE NEGOCIO ---
    if producto.categoria == CategoriaProducto.GRANO and movimiento.tipo == TipoMovimiento.ENTRADA:
        query = select(Movimiento).where(
            Movimiento.producto_id == movimiento.producto_id,
            Movimiento.periodo_id == movimiento.periodo_id,
            Movimiento.tipo == TipoMovimiento.ENTRADA
        )
        if session.exec(query).first():
            raise HTTPException(status_code=400, detail="El GRANO solo puede tener una entrada por periodo.")
        movimiento.semana_id = None

    elif producto.categoria == CategoriaProducto.GALERIA and movimiento.tipo == TipoMovimiento.ENTRADA:
        if not movimiento.semana_id:
            raise HTTPException(status_code=400, detail="Las entradas de GALERIA requieren semana.")

    if movimiento.tipo == TipoMovimiento.SALIDA:
        if not movimiento.destino_tipo:
            raise HTTPException(status_code=400, detail="Falta especificar RUTA o TERCERO.")
        if movimiento.destino_tipo == TipoDestino.TERCERO and not movimiento.nota_terceros:
             raise HTTPException(status_code=400, detail="Nota obligatoria para terceros.")
        if movimiento.destino_tipo == TipoDestino.RUTA and not movimiento.ruta_nombre:
             raise HTTPException(status_code=400, detail="Nombre de ruta obligatorio.")

    db_movimiento = Movimiento.model_validate(movimiento)
    session.add(db_movimiento)
    session.commit()
    session.refresh(db_movimiento)
    return db_movimiento

# --- ENDPOINT OPTIMIZADO: PAGINACIÓN Y FILTRADO ---
@router.get("/", response_model=Page[MovimientoRead]) # <--- Usamos Page[...]
def listar_movimientos(
    session: Session = Depends(get_session),
    # 2. Inyectamos la paginación automática (page, limit)
    pagination: PaginationParams = Depends(), 
    # 3. Filtros opcionales
    search: Optional[str] = None,
    tipo: Optional[TipoMovimiento] = None,
    periodo_id: Optional[int] = None,
    semana_id: Optional[int] = None,
    ruta_nombre: Optional[str] = None,
    destino_tipo: Optional[TipoDestino] = None
):
    # A. Construir la Query Base (con Join para buscar por nombre de producto)
    query = select(Movimiento).join(Producto)

    # B. Aplicar Filtros Dinámicos
    if search:
        query = query.where(Producto.nombre.ilike(f"%{search}%"))
    if tipo:
        query = query.where(Movimiento.tipo == tipo)
    if periodo_id:
        query = query.where(Movimiento.periodo_id == periodo_id)
    if semana_id:
        query = query.where(Movimiento.semana_id == semana_id)
    if ruta_nombre and ruta_nombre != 'todos':
        query = query.where(Movimiento.ruta_nombre == ruta_nombre)
    if destino_tipo:
        query = query.where(Movimiento.destino_tipo == destino_tipo)

    # C. Ordenar (Más reciente primero)
    query = query.order_by(desc(Movimiento.fecha))

    # D. ¡MAGIA! Paginar y retornar
    return paginate(session, query, pagination)

@router.patch("/{movimiento_id}", response_model=MovimientoRead)
def actualizar_movimiento(
    movimiento_id: int, 
    movimiento_data: MovimientoUpdate, 
    session: Session = Depends(get_session)
):
    db_movimiento = session.get(Movimiento, movimiento_id)
    if not db_movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    update_data = movimiento_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_movimiento, key, value)

    # RE-VALIDAR INTEGRIDAD
    producto = session.get(Producto, db_movimiento.producto_id)
    
    if producto.categoria == CategoriaProducto.GRANO and db_movimiento.tipo == TipoMovimiento.ENTRADA:
        query = select(Movimiento).where(
            Movimiento.producto_id == db_movimiento.producto_id,
            Movimiento.periodo_id == db_movimiento.periodo_id,
            Movimiento.tipo == TipoMovimiento.ENTRADA,
            Movimiento.id != movimiento_id
        )
        if session.exec(query).first():
            raise HTTPException(status_code=400, detail="Ya existe otra entrada de GRANO en este periodo.")
        db_movimiento.semana_id = None

    if producto.categoria == CategoriaProducto.GALERIA and db_movimiento.tipo == TipoMovimiento.ENTRADA:
        if not db_movimiento.semana_id:
            raise HTTPException(status_code=400, detail="Falta semana para GALERIA.")

    if db_movimiento.tipo == TipoMovimiento.SALIDA:
        if not db_movimiento.destino_tipo:
            raise HTTPException(status_code=400, detail="Falta destino.")
        if db_movimiento.destino_tipo == TipoDestino.TERCERO and not db_movimiento.nota_terceros:
            raise HTTPException(status_code=400, detail="Nota requerida.")
        if db_movimiento.destino_tipo == TipoDestino.RUTA and not db_movimiento.ruta_nombre:
            raise HTTPException(status_code=400, detail="Ruta requerida.")

    session.add(db_movimiento)
    session.commit()
    session.refresh(db_movimiento)
    return db_movimiento

@router.delete("/{movimiento_id}")
def eliminar_movimiento(movimiento_id: int, session: Session = Depends(get_session)):
    db_movimiento = session.get(Movimiento, movimiento_id)
    if not db_movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    session.delete(db_movimiento)
    session.commit()
    return {"mensaje": "Movimiento eliminado correctamente"}