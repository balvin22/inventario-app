from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.inventory import Periodo, Semana
from app.schemas.inventory import PeriodoCreate, PeriodoRead, SemanaCreate, SemanaRead

router = APIRouter(prefix="/periodos", tags=["Periodos y Semanas"])

# --- PERIODOS ---

@router.get("/", response_model=list[PeriodoRead])
def listar_periodos(session: Session = Depends(get_session)):
    return session.exec(select(Periodo)).all()

@router.post("/", response_model=PeriodoRead)
def crear_periodo(periodo: PeriodoCreate, session: Session = Depends(get_session)):
    db_periodo = Periodo.model_validate(periodo)
    session.add(db_periodo)
    session.commit()
    session.refresh(db_periodo)
    return db_periodo

@router.put("/{id}", response_model=PeriodoRead)
def actualizar_periodo(id: int, datos: PeriodoCreate, session: Session = Depends(get_session)):
    db_obj = session.get(Periodo, id)
    if not db_obj: raise HTTPException(404, "Periodo no encontrado")
    for k, v in datos.model_dump(exclude_unset=True).items(): setattr(db_obj, k, v)
    session.add(db_obj); session.commit(); session.refresh(db_obj)
    return db_obj

@router.delete("/{id}")
def eliminar_periodo(id: int, session: Session = Depends(get_session)):
    db_obj = session.get(Periodo, id)
    if not db_obj: raise HTTPException(404, "Periodo no encontrado")
    session.delete(db_obj); session.commit()
    return {"ok": True}

# --- SEMANAS ---

@router.get("/{periodo_id}/semanas", response_model=list[SemanaRead])
def listar_semanas(periodo_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Semana).where(Semana.periodo_id == periodo_id)).all()

@router.post("/{periodo_id}/semanas", response_model=SemanaRead)
def crear_semana(periodo_id: int, semana: SemanaCreate, session: Session = Depends(get_session)):
    semana.periodo_id = periodo_id
    db_semana = Semana.model_validate(semana)
    session.add(db_semana); session.commit(); session.refresh(db_semana)
    return db_semana

# Nota: Usamos una ruta especial para editar/borrar semanas por su ID único
@router.put("/semanas/{semana_id}", response_model=SemanaRead)
def actualizar_semana(semana_id: int, datos: SemanaCreate, session: Session = Depends(get_session)):
    db_obj = session.get(Semana, semana_id)
    if not db_obj: raise HTTPException(404, "Semana no encontrada")
    for k, v in datos.model_dump(exclude_unset=True).items(): setattr(db_obj, k, v)
    session.add(db_obj); session.commit(); session.refresh(db_obj)
    return db_obj

@router.delete("/semanas/{semana_id}")
def eliminar_semana(semana_id: int, session: Session = Depends(get_session)):
    db_obj = session.get(Semana, semana_id)
    if not db_obj: raise HTTPException(404, "Semana no encontrada")
    session.delete(db_obj); session.commit()
    return {"ok": True}