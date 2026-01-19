from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from app.db.session import get_session
from typing import Optional
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
from app.models.inventory import Movimiento, TipoMovimiento, Producto, Periodo, Semana, TipoDestino

router = APIRouter(prefix="/reportes", tags=["Reportes e Indicadores"])

# 1. Endpoint para saber el STOCK ACTUAL de un producto
@router.get("/stock/{producto_id}")
def obtener_stock_actual(producto_id: int, session: Session = Depends(get_session)):
    query_entradas = select(func.sum(Movimiento.cantidad)).where(
        Movimiento.producto_id == producto_id,
        Movimiento.tipo == TipoMovimiento.ENTRADA
    )
    total_entradas = session.exec(query_entradas).one() or 0

    query_salidas = select(func.sum(Movimiento.cantidad)).where(
        Movimiento.producto_id == producto_id,
        Movimiento.tipo == TipoMovimiento.SALIDA
    )
    total_salidas = session.exec(query_salidas).one() or 0

    stock_actual = total_entradas - total_salidas

    return {
        "producto_id": producto_id,
        "total_entradas": total_entradas,
        "total_salidas": total_salidas,
        "stock_disponible": stock_actual
    }

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
def reporte_matrix_global(session: Session = Depends(get_session)):
    periodos = session.exec(select(Periodo).order_by(Periodo.fecha_inicio)).all()
    productos = session.exec(select(Producto)).all()
    
    matrix = []
    
    for prod in productos:
        fila = {
            "producto_id": prod.id,
            "nombre": prod.nombre,
            "categoria": prod.categoria,
            "periodos": {},
            # Ahora guardamos el detalle completo global, no solo el balance
            "global": {"entradas": 0, "salidas": 0, "balance": 0} 
        }
        
        g_in = 0
        g_out = 0
        tiene_movimiento = False
        
        for per in periodos:
            q_in = select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, Movimiento.periodo_id == per.id, Movimiento.tipo == TipoMovimiento.ENTRADA
            )
            q_out = select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, Movimiento.periodo_id == per.id, Movimiento.tipo == TipoMovimiento.SALIDA
            )
            
            t_in = session.exec(q_in).one() or 0
            t_out = session.exec(q_out).one() or 0
            balance = t_in - t_out
            
            if t_in > 0 or t_out > 0: tiene_movimiento = True
            
            fila["periodos"][per.id] = {
                "entradas": t_in,
                "salidas": t_out,
                "balance": balance
            }
            
            # Acumulamos al global
            g_in += t_in
            g_out += t_out

        fila["global"] = {
            "entradas": g_in,
            "salidas": g_out,
            "balance": g_in - g_out
        }
        
        if tiene_movimiento:
            matrix.append(fila)
            
    return {
        "headers": [{"id": p.id, "nombre": p.nombre} for p in periodos],
        "data": matrix
    }
    
# 3. MATRIZ SEMANAL POR PERIODO
@router.get("/dashboard/matrix/{periodo_id}")
def reporte_matrix_semanal(periodo_id: int, session: Session = Depends(get_session)):
    # 1. Obtener semanas y productos
    semanas = session.exec(select(Semana).where(Semana.periodo_id == periodo_id).order_by(Semana.numero)).all()
    productos = session.exec(select(Producto)).all()
    
    matrix = []
    
    for prod in productos:
        fila = {
            "producto_id": prod.id,
            "nombre": prod.nombre,
            "categoria": prod.categoria,
            "semanas": {},
            "resumen": {"entradas": 0, "salidas": 0, "balance": 0}
        }
        
        # --- CALCULAR TOTALES DEL PERIODO ---
        movs_periodo = session.exec(select(Movimiento).where(
            Movimiento.producto_id == prod.id,
            Movimiento.periodo_id == periodo_id
        )).all()

        t_in = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.ENTRADA)
        t_out = sum(m.cantidad for m in movs_periodo if m.tipo == TipoMovimiento.SALIDA)
        
        fila["resumen"] = {
            "entradas": t_in, 
            "salidas": t_out, 
            "balance": t_in - t_out
        }

        # --- DESGLOSE SEMANAL CON RUTAS ---
        hay_movimiento_semanal = False
        
        # Identificamos la primera semana del periodo para asignar los granos allí
        primera_sem_id = semanas[0].id if semanas else None
        
        for sem in semanas:
            # LÓGICA ESPECIAL PARA GRANO:
            # Si el producto es 'grano', ignoramos la semana real y lo asignamos todo a la Semana 1.
            # Si es 'galeria', respetamos la semana de la base de datos.
            
            if prod.categoria == 'grano':
                if sem.id == primera_sem_id:
                    movs_semana = movs_periodo # ¡Truco! Asignamos todo el periodo a la semana 1
                else:
                    movs_semana = [] # Las demás semanas van vacías para grano
            else:
                # Lógica normal para Galería (filtrar por ID de semana)
                movs_semana = [m for m in movs_periodo if m.semana_id == sem.id]

            val_in = sum(m.cantidad for m in movs_semana if m.tipo == TipoMovimiento.ENTRADA)
            val_out = sum(m.cantidad for m in movs_semana if m.tipo == TipoMovimiento.SALIDA)
            
            # Agrupar salidas por ruta
            detalles_rutas = {} 
            for m in movs_semana:
                if m.tipo == TipoMovimiento.SALIDA:
                    nombre_clave = m.ruta_nombre if m.destino_tipo == TipoDestino.RUTA else (f"Terceros: {m.nota_terceros}" if m.nota_terceros else "Terceros")
                    if not nombre_clave: nombre_clave = "Sin ruta"
                    detalles_rutas[nombre_clave] = detalles_rutas.get(nombre_clave, 0) + m.cantidad

            if val_in > 0 or val_out > 0: hay_movimiento_semanal = True
            
            fila["semanas"][sem.numero] = {
                "entradas": val_in, 
                "salidas": val_out,
                "rutas": detalles_rutas
            }
            
        if t_in > 0 or t_out > 0 or hay_movimiento_semanal:
            matrix.append(fila)
            
    return {
        "semanas_header": [s.numero for s in semanas],
        "data": matrix
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
def exportar_inventario_excel(session: Session = Depends(get_session)):
    # 1. Obtener datos (Reutilizamos la lógica de la matriz global)
    periodos = session.exec(select(Periodo).order_by(Periodo.fecha_inicio)).all()
    productos = session.exec(select(Producto)).all()
    
    data_para_excel = []
    
    for prod in productos:
        # Fila base
        fila = {
            "ID": prod.id,
            "Producto": prod.nombre,
            "Categoría": prod.categoria.capitalize(),
        }
        
        balance_global = 0
        g_in = 0
        g_out = 0
        
        # Iterar periodos para llenar columnas dinámicas (Periodo 1, Periodo 2...)
        for per in periodos:
            # Calcular movimientos del periodo
            q_in = select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.ENTRADA
            )
            q_out = select(func.sum(Movimiento.cantidad)).where(
                Movimiento.producto_id == prod.id, 
                Movimiento.periodo_id == per.id, 
                Movimiento.tipo == TipoMovimiento.SALIDA
            )
            
            t_in = session.exec(q_in).one() or 0
            t_out = session.exec(q_out).one() or 0
            balance = t_in - t_out
            
            g_in += t_in
            g_out += t_out
            balance_global += balance
            
            # Agregamos columnas dinámicas al Excel
            # Esto creará columnas como: "Enero (Entradas)", "Enero (Salidas)", "Enero (Balance)"
            fila[f"{per.nombre} (Ent)"] = t_in
            fila[f"{per.nombre} (Sal)"] = t_out
            fila[f"{per.nombre} (Balance)"] = balance

        # Agregar los totales históricos al final
        fila["Total Entradas Hist."] = g_in
        fila["Total Salidas Hist."] = g_out
        fila["Balance Global"] = balance_global
        
        data_para_excel.append(fila)

    # 2. Crear DataFrame de Pandas
    df = pd.DataFrame(data_para_excel)
    
    # 3. Generar el archivo Excel en memoria (buffer)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario General')
        
        # (Opcional) Ajuste automático del ancho de columnas para que se vea bonito
        worksheet = writer.sheets['Inventario General']
        for idx, col in enumerate(df.columns):
            max_len = max((df[col].astype(str).map(len).max(), len(str(col)))) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len

    output.seek(0)

    # 4. Retornar como descarga
    headers = {
        'Content-Disposition': 'attachment; filename="Reporte_Inventario_Completo.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')