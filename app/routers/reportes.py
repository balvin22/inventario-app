from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from app.db.session import get_session
from openpyxl.utils import get_column_letter
from typing import Optional
import pandas as pd
import math
from io import BytesIO
from fastapi.responses import StreamingResponse
from app.core.pagination import Page
from app.schemas.inventory import StockItem
from app.models.inventory import Movimiento, TipoMovimiento, Producto, Periodo, Semana, TipoDestino

router = APIRouter(prefix="/reportes", tags=["Reportes e Indicadores"])

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
    # Contamos total de productos que cumplen el filtro
    total_count = session.exec(select(func.count()).select_from(query.subquery())).one()
    
    # Calculamos offset
    offset = (page - 1) * limit
    total_pages = math.ceil(total_count / limit)
    
    # Traemos solo los productos de esta página
    productos_pagina = session.exec(query.offset(offset).limit(limit)).all()
    
    # C. Calcular Stock para estos productos
    reporte_data = []
    
    for prod in productos_pagina:
        # Sumar entradas
        entradas = session.exec(select(func.sum(Movimiento.cantidad)).where(
            Movimiento.producto_id == prod.id,
            Movimiento.tipo == TipoMovimiento.ENTRADA
        )).one() or 0
        
        # Sumar salidas
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
    # --- NUEVOS PARÁMETROS ---
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    periodo_id: Optional[int] = None
):
    # A. Obtener Headers (Periodos)
    # Si filtran por periodo_id, solo mostramos ese periodo en el header
    query_periodos = select(Periodo).order_by(Periodo.fecha_inicio)
    if periodo_id:
        query_periodos = query_periodos.where(Periodo.id == periodo_id)
    
    periodos = session.exec(query_periodos).all()
    
    # B. Paginar las Filas (Productos) - APLICANDO FILTROS
    query_prod = select(Producto)
    
    # Filtro Búsqueda (Nombre)
    if search:
        query_prod = query_prod.where(Producto.nombre.ilike(f"%{search}%"))
    
    # Filtro Categoría
    if categoria and categoria != 'all':
        query_prod = query_prod.where(Producto.categoria == categoria)
    
    # Contar total productos filtrados
    total_count = session.exec(select(func.count()).select_from(query_prod.subquery())).one()
    
    # Paginación
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
            # Consultar movimientos para este producto y periodo
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

        # IMPORTANTE: Si se filtra por periodo, el "global" debería reflejar solo lo visible?
        # Generalmente "Global" significa "Total Histórico" independiente de la vista,
        # pero si el usuario filtra por periodo, a veces espera ver el total de ESE periodo.
        # Para mantener consistencia con "Histórico", dejaremos que calcule sumando lo visible
        # si se filtró por periodo, o todo si no.
        # En este bucle ya estamos sumando solo los periodos visibles (variable 'periodos'),
        # así que el total global será coherente con las columnas mostradas.

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
    limit: int = Query(10, le=100) # Límite por defecto para el detalle
):
    # A. Obtener Headers (Semanas) - No se paginan
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
        
        # Totales del periodo para este producto
        movs_periodo = session.exec(select(Movimiento).where(
            Movimiento.producto_id == prod.id,
            Movimiento.periodo_id == periodo_id
        )).all()

        t_in = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.ENTRADA)
        t_out = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.SALIDA)
        fila["resumen"] = { "entradas": t_in, "salidas": t_out, "balance": t_in - t_out }

        # Desglose Semanal
        hay_movimiento = False
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

            if val_in > 0 or val_out > 0: hay_movimiento = True
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
        
        # --- AQUÍ ESTABA EL ERROR, ESTA ES LA CORRECCIÓN ---
        for idx, col in enumerate(df.columns):
            max_len = 0
            if not df.empty:
                series_len = df[col].astype(str).map(len).max()
                if pd.isna(series_len): series_len = 0
                max_len = max(series_len, len(str(col))) + 2
            else:
                max_len = len(str(col)) + 5
            
            final_width = min(max_len, 50) 
            
            # Usamos get_column_letter en lugar de chr()
            # idx + 1 porque get_column_letter es base 1 (1=A)
            col_letter = get_column_letter(idx + 1) 
            worksheet.column_dimensions[col_letter].width = final_width
        # ---------------------------------------------------

    output.seek(0)

    headers = {
        'Content-Disposition': 'attachment; filename="Reporte_Inventario.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')