from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.inventory import Ruta
from app.schemas.inventory import RutaCreate, RutaRead

router = APIRouter(prefix="/rutas", tags=["Catálogo de Rutas"])

@router.get("/", response_model=list[RutaRead])
def listar_rutas(session: Session = Depends(get_session)):
    return session.exec(select(Ruta).where(Ruta.activa == True)).all()

@router.post("/", response_model=RutaRead)
def crear_ruta(ruta: RutaCreate, session: Session = Depends(get_session)):
    db_ruta = Ruta.model_validate(ruta)
    session.add(db_ruta)
    session.commit()
    session.refresh(db_ruta)
    return db_ruta

@router.put("/{ruta_id}", response_model=RutaRead)
def actualizar_ruta(ruta_id: int, ruta_data: RutaCreate, session: Session = Depends(get_session)):
    db_ruta = session.get(Ruta, ruta_id)
    if not db_ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    
    data = ruta_data.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(db_ruta, key, value)
        
    session.add(db_ruta)
    session.commit()
    session.refresh(db_ruta)
    return db_ruta

@router.delete("/{ruta_id}")
def eliminar_ruta(ruta_id: int, session: Session = Depends(get_session)):
    db_ruta = session.get(Ruta, ruta_id)
    if not db_ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    
    # Soft delete
    db_ruta.activa = False 
    session.add(db_ruta)
    session.commit()
    return {"mensaje": "Ruta eliminada (Soft Delete)"}