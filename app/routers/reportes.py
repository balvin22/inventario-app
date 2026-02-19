from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlmodel import Session, select, func
from app.db.session import get_session
from openpyxl.utils import get_column_letter
from typing import Optional, List
from pydantic import BaseModel
import pandas as pd
import math
from io import BytesIO
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.core.pagination import Page
from app.schemas.inventory import StockItem
from app.models.inventory import Movimiento, TipoMovimiento, Producto, Periodo, Semana, TipoDestino

# --- IMPORTANTE: Importamos el servicio que creamos para generar el PDF ---
# Si aún no has creado el archivo en app/services/pdf_service.py, esto dará error.
from app.services.pdf_service import generar_pdf_entrega

router = APIRouter(prefix="/reportes", tags=["Reportes e Indicadores"])

class DatosActaGlobal(BaseModel):
    folio_id: str
    project_name: str
    responsable_entrega_nombre: str
    responsable_entrega_cargo: str
    responsable_recibe_nombre: str
    responsable_recibe_cargo: str
    # Filtros para que el backend busque TODO
    search: Optional[str] = None
    categoria: Optional[str] = None
    periodo_id: Optional[int] = None

# 1. Endpoint para saber el STOCK ACTUAL de un producto
@router.get("/inventario-paginado", response_model=Page[StockItem])
def reporte_inventario_paginado(
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    search: Optional[str] = None
):
    # A. Query Base sobre PRODUCTOS
    query = select(Producto)
    
    if search:
        query = query.where(Producto.nombre.ilike(f"%{search}%"))
        
    # B. Paginación Manual (Porque necesitamos calcular stock después)
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    
    offset = (page - 1) * limit
    total_pages = math.ceil(total_count / limit)
    
    productos_pagina = session.exec(query.offset(offset).limit(limit)).all()
    
    # C. Calcular Stock para estos productos
    reporte_data = []
    
    for prod in productos_pagina:
        entradas = session.exec(select(func.sum(Movimiento.cantidad)).where(
            Movimiento.producto_id == prod.id,
            Movimiento.tipo == TipoMovimiento.ENTRADA
        )).one() or 0
        
        salidas = session.exec(select(func.sum(Movimiento.cantidad)).where(
            Movimiento.producto_id == prod.id,
            Movimiento.tipo == TipoMovimiento.SALIDA
        )).one() or 0
        
        stock = entradas - salidas
        
        reporte_data.append(StockItem(
            producto_id=prod.id,
            nombre=prod.nombre,
            categoria=prod.categoria,
            total_entradas=entradas,
            total_salidas=salidas,
            stock_actual=stock
        ))
        
    # D. Retornar estructura Page
    return Page(
        data=reporte_data,
        total=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

# 2. Dashboard Normal (Lista simple o filtrada por semana)
@router.get("/dashboard/{periodo_id}")
def reporte_dashboard_periodo(
    periodo_id: int, 
    semana_id: Optional[int] = None, 
    session: Session = Depends(get_session)
):
    productos = session.exec(select(Producto)).all()
    reporte = []
    
    for prod in productos:
        query_entradas = select(func.sum(Movimiento.cantidad)).where(
            Movimiento.producto_id == prod.id,
            Movimiento.periodo_id == periodo_id,
            Movimiento.tipo == TipoMovimiento.ENTRADA
        )
        
        query_salidas = select(func.sum(Movimiento.cantidad)).where(
            Movimiento.producto_id == prod.id,
            Movimiento.periodo_id == periodo_id,
            Movimiento.tipo == TipoMovimiento.SALIDA
        )

        if semana_id:
            query_entradas = query_entradas.where(Movimiento.semana_id == semana_id)
            query_salidas = query_salidas.where(Movimiento.semana_id == semana_id)

        total_entradas = session.exec(query_entradas).one() or 0
        total_salidas = session.exec(query_salidas).one() or 0
        balance = total_entradas - total_salidas
        
        if total_entradas > 0 or total_salidas > 0:
            reporte.append({
                "producto_id": prod.id,
                "producto_nombre": prod.nombre,
                "categoria": prod.categoria,
                "entradas": total_entradas,
                "salidas": total_salidas,
                "balance": balance
            })
            
    return reporte

# MATRIZ GLOBAL (TODOS LOS PERIODOS)
@router.get("/dashboard/matrix/global")
def reporte_matrix_global(
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=100),
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    periodo_id: Optional[int] = None
):
    # A. Obtener Headers (Periodos)
    query_periodos = select(Periodo).order_by(Periodo.fecha_inicio)
    if periodo_id:
        query_periodos = query_periodos.where(Periodo.id == periodo_id)
    
    periodos = session.exec(query_periodos).all()
    
    # B. Paginar las Filas (Productos)
    query_prod = select(Producto)
    
    if search:
        query_prod = query_prod.where(Producto.nombre.ilike(f"%{search}%"))
    
    if categoria and categoria != 'all':
        query_prod = query_prod.where(Producto.categoria == categoria)
    
    total_count = session.exec(select(func.count()).select_from(query_prod.subquery())).one()
    
    total_pages = math.ceil(total_count / limit) if limit > 0 else 1
    offset = (page - 1) * limit
    
    productos_pagina = session.exec(query_prod.order_by(Producto.id).offset(offset).limit(limit)).all()
    
    # C. Construir la data
    matrix = []
    
    for prod in productos_pagina:
        fila = {
            "producto_id": prod.id,
            "nombre": prod.nombre,
            "categoria": prod.categoria,
            "periodos": {},
            "global": {"entradas": 0, "salidas": 0, "balance": 0} 
        }
        
        g_in = 0
        g_out = 0
        
        for per in periodos:
            t_in = session.exec(select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.ENTRADA
            )).one() or 0
            
            t_out = session.exec(select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.SALIDA
            )).one() or 0
            
            fila["periodos"][per.id] = { "entradas": t_in, "salidas": t_out, "balance": t_in - t_out }
            g_in += t_in
            g_out += t_out

        fila["global"] = { "entradas": g_in, "salidas": g_out, "balance": g_in - g_out }
        matrix.append(fila)
            
    return {
        "headers": [{"id": p.id, "nombre": p.nombre} for p in periodos],
        "data": matrix,
        "pagination": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }
    }
    
# 3. MATRIZ SEMANAL POR PERIODO
@router.get("/dashboard/matrix/{periodo_id}")
def reporte_matrix_semanal(
    periodo_id: int, 
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=100)
):
    # A. Obtener Headers (Semanas)
    semanas = session.exec(select(Semana).where(Semana.periodo_id == periodo_id).order_by(Semana.numero)).all()
    
    # B. Paginar Productos
    query_prod = select(Producto)
    total_count = session.exec(select(func.count()).select_from(query_prod.subquery())).one()
    total_pages = math.ceil(total_count / limit)
    offset = (page - 1) * limit
    
    productos_pagina = session.exec(query_prod.order_by(Producto.id).offset(offset).limit(limit)).all()
    
    # C. Construir Data
    matrix = []
    
    for prod in productos_pagina:
        fila = {
            "producto_id": prod.id,
            "nombre": prod.nombre,
            "categoria": prod.categoria,
            "semanas": {},
            "resumen": {"entradas": 0, "salidas": 0, "balance": 0}
        }
        
        movs_periodo = session.exec(select(Movimiento).where(
            Movimiento.producto_id == prod.id,
            Movimiento.periodo_id == periodo_id
        )).all()

        t_in = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.ENTRADA)
        t_out = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.SALIDA)
        fila["resumen"] = { "entradas": t_in, "salidas": t_out, "balance": t_in - t_out }

        primera_sem_id = semanas[0].id if semanas else None
        
        for sem in semanas:
            if prod.categoria == 'grano':
                movs_semana = movs_periodo if sem.id == primera_sem_id else []
            else:
                movs_semana = [m for m in movs_periodo if m.semana_id == sem.id]

            val_in = sum(m.cantidad for m in movs_semana if m.tipo == TipoMovimiento.ENTRADA)
            val_out = sum(m.cantidad for m in movs_semana if m.tipo == TipoMovimiento.SALIDA)
            
            detalles_rutas = {} 
            for m in movs_semana:
                if m.tipo == TipoMovimiento.SALIDA:
                    nombre = m.ruta_nombre if m.destino_tipo == TipoDestino.RUTA else (f"Terceros: {m.nota_terceros}" if m.nota_terceros else "Terceros") or "Sin ruta"
                    detalles_rutas[nombre] = detalles_rutas.get(nombre, 0) + m.cantidad

            fila["semanas"][sem.numero] = { "entradas": val_in, "salidas": val_out, "rutas": detalles_rutas }
            
        matrix.append(fila)
            
    return {
        "semanas_header": [s.numero for s in semanas],
        "data": matrix,
        "pagination": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }
    }

# 4. Reporte Consumo Ruta
@router.get("/consumo-ruta")
def reporte_consumo_ruta(
    ruta_nombre: str, 
    periodo_id: int, 
    semana_id: int = None, 
    session: Session = Depends(get_session)
):
    query = select(Movimiento.producto_id, func.sum(Movimiento.cantidad).label("total_gastado"))\
        .where(
            Movimiento.tipo == TipoMovimiento.SALIDA,
            Movimiento.ruta_nombre == ruta_nombre,
            Movimiento.periodo_id == periodo_id
        )\
        .group_by(Movimiento.producto_id)

    if semana_id:
        query = query.where(Movimiento.semana_id == semana_id)

    resultados = session.exec(query).all()

    reporte = []
    for prod_id, total in resultados:
        nombre_prod = session.get(Producto, prod_id).nombre
        reporte.append({
            "producto": nombre_prod,
            "cantidad_gastada": total
        })

    return {
        "ruta": ruta_nombre,
        "periodo_id": periodo_id,
        "semana_id": semana_id,
        "detalle": reporte
    }
    
@router.get("/exportar-excel")
def exportar_inventario_excel(
    session: Session = Depends(get_session),
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    periodo_id: Optional[int] = None
):
    # 1. Obtener Periodos
    query_periodos = select(Periodo).order_by(Periodo.fecha_inicio)
    if periodo_id:
        query_periodos = query_periodos.where(Periodo.id == periodo_id)
    periodos = session.exec(query_periodos).all()

    # 2. Obtener Productos
    query_prod = select(Producto)
    if search:
        query_prod = query_prod.where(Producto.nombre.ilike(f"%{search}%"))
    if categoria and categoria != 'all':
        query_prod = query_prod.where(Producto.categoria == categoria)
        
    productos = session.exec(query_prod).all()
    
    data_para_excel = []
    
    for prod in productos:
        fila = {
            "ID": prod.id,
            "Producto": prod.nombre,
            "Categoría": prod.categoria.capitalize(),
        }
        
        balance_global = 0
        g_in = 0
        g_out = 0
        
        for per in periodos:
            t_in = session.exec(select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.ENTRADA
            )).one() or 0
            
            t_out = session.exec(select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.SALIDA
            )).one() or 0
            
            balance = t_in - t_out
            g_in += t_in
            g_out += t_out
            balance_global += balance
            
            fila[f"{per.nombre} (Ent)"] = t_in
            fila[f"{per.nombre} (Sal)"] = t_out
            fila[f"{per.nombre} (Balance)"] = balance

        fila["Total Entradas"] = g_in
        fila["Total Salidas"] = g_out
        fila["Balance Total"] = balance_global
        
        data_para_excel.append(fila)

    # 3. Generar Excel
    df = pd.DataFrame(data_para_excel)
    output = BytesIO()
    
    if df.empty:
        df = pd.DataFrame(columns=["ID", "Producto", "Mensaje"])
        df.loc[0] = ["-", "-", "No se encontraron datos con los filtros aplicados"]

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario Filtrado')
        
        worksheet = writer.sheets['Inventario Filtrado']
        
        for idx, col in enumerate(df.columns):
            max_len = 0
            if not df.empty:
                series_len = df[col].astype(str).map(len).max()
                if pd.isna(series_len): series_len = 0
                max_len = max(series_len, len(str(col))) + 2
            else:
                max_len = len(str(col)) + 5
            
            final_width = min(max_len, 50) 
            col_letter = get_column_letter(idx + 1) 
            worksheet.column_dimensions[col_letter].width = final_width

    output.seek(0)

    headers = {
        'Content-Disposition': 'attachment; filename="Reporte_Inventario.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@router.post("/descargar-acta-pdf")
def descargar_acta_entrega(
    datos: DatosActaGlobal,
    session: Session = Depends(get_session)
):
    """
    Recibe filtros, recalcula todo el inventario (SIN paginación) y genera el PDF.
    """
    try:
        # --- A. LÓGICA DE BÚSQUEDA (Copia de Matrix Global pero SIN LIMIT/OFFSET) ---
        
        # 1. Obtener Periodos
        query_periodos = select(Periodo).order_by(Periodo.fecha_inicio)
        if datos.periodo_id and datos.periodo_id != 0: # Asumiendo que 0 o None es 'todos'
            query_periodos = query_periodos.where(Periodo.id == datos.periodo_id)
        periodos = session.exec(query_periodos).all()
        
        # 2. Obtener TODOS los Productos filtrados
        query_prod = select(Producto)
        if datos.search:
            query_prod = query_prod.where(Producto.nombre.ilike(f"%{datos.search}%"))
        if datos.categoria and datos.categoria != 'all':
            query_prod = query_prod.where(Producto.categoria == datos.categoria)
            
        # ¡AQUÍ ESTÁ LA CLAVE! -> .all() sin .limit() ni .offset()
        todos_productos = session.exec(query_prod.order_by(Producto.nombre)).all()
        
        # --- B. CALCULAR SALDOS (Bucle masivo) ---
        items_para_pdf = []
        
        for prod in todos_productos:
            g_in = 0
            g_out = 0
            
            # Sumamos movimientos de los periodos seleccionados
            for per in periodos:
                # OPTIMIZACIÓN: Podríamos hacer una sola query grande antes, 
                # pero para mantener consistencia usamos la lógica existente.
                t_in = session.exec(select(func.sum(Movimiento.cantidad)).where(
                    Movimiento.producto_id == prod.id, 
                    Movimiento.periodo_id == per.id, 
                    Movimiento.tipo == TipoMovimiento.ENTRADA
                )).one() or 0
                
                t_out = session.exec(select(func.sum(Movimiento.cantidad)).where(
                    Movimiento.producto_id == prod.id, 
                    Movimiento.periodo_id == per.id, 
                    Movimiento.tipo == TipoMovimiento.SALIDA
                )).one() or 0
                
                g_in += t_in
                g_out += t_out

            balance = g_in - g_out
            
            # Agregamos a la lista solo si quieres mostrar todo, 
            # o podrías filtrar los que tienen movimiento (opcional)
            items_para_pdf.append({
                "ref": str(prod.id),
                "description": prod.nombre,
                "quantity": balance,
                "status": f"Ent: {g_in} | Sal: {g_out}"
            })

        # --- C. PREPARAR DATOS PARA JINJA ---
        data_dict = datos.dict()
        data_dict["items"] = items_para_pdf # Inyectamos la lista calculada
        data_dict["date"] = datetime.now().strftime("%d/%m/%Y")
        
        # --- D. GENERAR PDF ---
        pdf_bytes = generar_pdf_entrega(data_dict)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Acta_Global_{datos.folio_id}.pdf"'
            }
        )
    except Exception as e:
        print(f"Error generando PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")