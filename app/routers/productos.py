from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.inventory import Producto
from app.schemas.inventory import ProductoCreate, ProductoRead

router = APIRouter(prefix="/productos", tags=["Productos"])

# 1. LISTAR (GET)
@router.get("/", response_model=list[ProductoRead])
def listar_productos(session: Session = Depends(get_session)):
    return session.exec(select(Producto)).all()

# 2. CREAR (POST)
@router.post("/", response_model=ProductoRead)
def crear_producto(producto: ProductoCreate, session: Session = Depends(get_session)):
    db_producto = Producto.model_validate(producto)
    session.add(db_producto)
    session.commit()
    session.refresh(db_producto)
    return db_producto

# 3. ACTUALIZAR (PUT) - NUEVO
@router.put("/{producto_id}", response_model=ProductoRead)
def actualizar_producto(producto_id: int, datos_nuevos: ProductoCreate, session: Session = Depends(get_session)):
    db_producto = session.get(Producto, producto_id)
    if not db_producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Actualizamos solo los campos que nos envían
    producto_data = datos_nuevos.model_dump(exclude_unset=True)
    for key, value in producto_data.items():
        setattr(db_producto, key, value)
        
    session.add(db_producto)
    session.commit()
    session.refresh(db_producto)
    return db_producto

# 4. ELIMINAR (DELETE) - NUEVO
@router.delete("/{producto_id}")
def eliminar_producto(producto_id: int, session: Session = Depends(get_session)):
    db_producto = session.get(Producto, producto_id)
    if not db_producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    session.delete(db_producto)
    session.commit()
    return {"mensaje": "Producto eliminado correctamente"}