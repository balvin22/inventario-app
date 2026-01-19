from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select
from app.db.session import get_session
from app.models.inventory import Movimiento, Producto, CategoriaProducto, TipoMovimiento, TipoDestino
from app.schemas.inventory import MovimientoCreate, MovimientoRead


router = APIRouter(prefix="/movimientos", tags=["Movimientos"])

@router.post("/", response_model=MovimientoRead)
def registrar_movimiento(movimiento: MovimientoCreate, session: Session = Depends(get_session)):
    # 1. Buscar el producto para saber si es GRANO o GALERIA
    producto = session.get(Producto, movimiento.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # --- VALIDACIONES DE NEGOCIO ---

    # CASO 1: Lógica para GRANO
    if producto.categoria == CategoriaProducto.GRANO:
        
        # Regla: Entradas solo una vez por periodo
        if movimiento.tipo == TipoMovimiento.ENTRADA:
            query = select(Movimiento).where(
                Movimiento.producto_id == movimiento.producto_id,
                Movimiento.periodo_id == movimiento.periodo_id,
                Movimiento.tipo == TipoMovimiento.ENTRADA
            )
            existe = session.exec(query).first()
            if existe:
                raise HTTPException(status_code=400, detail="El GRANO solo puede tener una entrada por periodo.")
            
            # Grano no usa semanas en entrada, limpiamos por seguridad
            movimiento.semana_id = None

    # CASO 2: Lógica para GALERIA
    elif producto.categoria == CategoriaProducto.GALERIA:
        
        # Regla: Entradas requieren semana obligatoria
        if movimiento.tipo == TipoMovimiento.ENTRADA:
            if not movimiento.semana_id:
                raise HTTPException(status_code=400, detail="Las entradas de GALERIA requieren especificar la semana.")

    # CASO 3: Validaciones Generales de Salida
    if movimiento.tipo == TipoMovimiento.SALIDA:
        if not movimiento.destino_tipo:
            raise HTTPException(status_code=400, detail="Debes especificar si la salida es por RUTA o TERCERO.")
            
        if movimiento.destino_tipo == TipoDestino.TERCERO and not movimiento.nota_terceros:
             raise HTTPException(status_code=400, detail="Las salidas a TERCEROS requieren una nota obligatoria.")
             
        if movimiento.destino_tipo == TipoDestino.RUTA and not movimiento.ruta_nombre:
             raise HTTPException(status_code=400, detail="Las salidas por RUTA requieren el nombre de la ruta.")

    # --- GUARDAR EN BD ---
    db_movimiento = Movimiento.model_validate(movimiento)
    session.add(db_movimiento)
    session.commit()
    session.refresh(db_movimiento)
    
    return db_movimiento

@router.get("/", response_model=list[MovimientoRead])
def listar_movimientos(session: Session = Depends(get_session)):
    # Traemos los movimientos ordenados del más reciente al más antiguo
    return session.exec(select(Movimiento).order_by(desc(Movimiento.fecha))).all()