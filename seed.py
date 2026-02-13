import random
from datetime import datetime, timedelta
from sqlmodel import Session, select, delete
from faker import Faker
from app.db.session import engine 
from app.models.inventory import (
    Producto, CategoriaProducto, 
    Periodo, Semana, Ruta, 
    Movimiento, TipoMovimiento, TipoDestino
)

# Configuración de Faker
fake = Faker('es_CO') 

def create_periodos_semanas(session: Session):
    print("📅 Creando 12 Periodos (Meses) y sus Semanas...")
    year = datetime.now().year
    periodos = []
    
    for month in range(1, 13):
        fecha_inicio = datetime(year, month, 1)
        # Calcular último día del mes
        if month == 12:
            fecha_fin = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            fecha_fin = datetime(year, month + 1, 1) - timedelta(days=1)
            
        nombre_mes = fecha_inicio.strftime("%B").capitalize()
        
        # Crear Periodo
        periodo = Periodo(
            nombre=f"{nombre_mes} {year}",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activo=True
        )
        session.add(periodo)
        session.commit()
        session.refresh(periodo)
        periodos.append(periodo)

        # Crear 4 semanas por periodo
        for i in range(1, 5):
            w_start = fecha_inicio + timedelta(days=(i-1)*7)
            w_end = w_start + timedelta(days=6)
            if w_end > fecha_fin: w_end = fecha_fin
            
            semana = Semana(
                numero=i,
                fecha_inicio=w_start,
                fecha_fin=w_end,
                periodo_id=periodo.id
            )
            session.add(semana)
        session.commit()
    
    return periodos

def create_rutas(session: Session):
    print("🚚 Creando Rutas Maestras...")
    rutas_names = [
        "Ruta Norte", "Ruta Sur", "Ruta Centro", 
        "Vereda La Paz", "Vereda El Tambo", "Salida Popayán",
        "Vereda Cajibío", "Ruta Timbío", "Distribución Local"
    ]
    rutas = []
    for name in rutas_names:
        existe = session.exec(select(Ruta).where(Ruta.nombre == name)).first()
        if not existe:
            ruta = Ruta(nombre=name, descripcion=fake.sentence(), activa=True)
            session.add(ruta)
            rutas.append(ruta)
    session.commit()
    return session.exec(select(Ruta)).all()

def create_productos(session: Session):
    print("📦 Generando 100 Productos...")
    
    # 1. Algunos productos reales para que se vea bonito
    productos_data = [
        ("Arroz Libra", CategoriaProducto.GRANO),
        ("Arroz Bulto 50kg", CategoriaProducto.GRANO),
        ("Aceite 1L", CategoriaProducto.GRANO),
        ("Aceite 3L", CategoriaProducto.GRANO),
        ("Frijol Bola Roja", CategoriaProducto.GRANO),
        ("Lenteja", CategoriaProducto.GRANO),
        ("Azúcar Manuelita", CategoriaProducto.GRANO),
        ("Sal Refisal", CategoriaProducto.GRANO),
        ("Panela", CategoriaProducto.GALERIA),
        ("Papa Parda", CategoriaProducto.GALERIA),
        ("Papa Criolla", CategoriaProducto.GALERIA),
        ("Cebolla Larga", CategoriaProducto.GALERIA),
        ("Cebolla Cabezona", CategoriaProducto.GALERIA),
        ("Tomate Chonto", CategoriaProducto.GALERIA),
        ("Zanahoria", CategoriaProducto.GALERIA),
        ("Plátano Verde", CategoriaProducto.GALERIA),
        ("Jabón Rey", CategoriaProducto.ASEO),
        ("Limpido", CategoriaProducto.ASEO),
        ("Papel Higiénico Familia", CategoriaProducto.ASEO),
        ("Detergente Fab", CategoriaProducto.ASEO),
    ]
    
    # 2. Rellenar hasta llegar a 100 con nombres generados
    faltantes = 100 - len(productos_data)
    
    adjetivos = ["Premium", "Especial", "Económico", "Grande", "Pequeño", "Familiar", "Industrial"]
    
    for _ in range(faltantes):
        cat = random.choice(list(CategoriaProducto))
        # Generar nombre tipo "Jabón Especial" o "Maíz Industrial"
        nombre_base = fake.word().capitalize()
        adjetivo = random.choice(adjetivos)
        name = f"{nombre_base} {adjetivo}"
        
        productos_data.append((name, cat))

    # Guardar en BD
    productos = []
    for nombre, cat in productos_data:
        prod = Producto(nombre=nombre, categoria=cat, descripcion=fake.sentence())
        session.add(prod)
        productos.append(prod)
    
    session.commit()
    return session.exec(select(Producto)).all()

def create_movimientos(session: Session, n=2000):
    print(f"📉 Generando {n} Movimientos (paciencia, estamos simulando trabajo duro)...")
    
    productos = session.exec(select(Producto)).all()
    periodos = session.exec(select(Periodo)).all()
    rutas = session.exec(select(Ruta)).all()
    
    # Preparamos lotes para insertar rápido
    batch = []
    
    for i in range(n):
        prod = random.choice(productos)
        periodo = random.choice(periodos)
        
        # Obtener semanas de ese periodo (simulado)
        semanas = session.exec(select(Semana).where(Semana.periodo_id == periodo.id)).all()
        semana = random.choice(semanas) if semanas else None
        
        tipo = random.choice([TipoMovimiento.ENTRADA, TipoMovimiento.SALIDA])
        
        # Cantidades más realistas según categoría
        if prod.categoria == CategoriaProducto.GRANO:
            cantidad = random.randint(1, 50) # Bultos o unidades
        else:
            cantidad = random.randint(10, 500) # Kilos o unidades pequeñas
            
        mov = Movimiento(
            fecha=fake.date_time_between(start_date="-1y", end_date="now"),
            cantidad=float(cantidad),
            tipo=tipo,
            producto_id=prod.id,
            periodo_id=periodo.id,
            semana_id=semana.id if semana else None
        )
        
        # --- REGLAS DE NEGOCIO ---
        if prod.categoria == CategoriaProducto.GRANO and tipo == TipoMovimiento.ENTRADA:
            mov.semana_id = None 
        
        if tipo == TipoMovimiento.SALIDA:
            destino = random.choice([TipoDestino.RUTA, TipoDestino.TERCERO])
            mov.destino_tipo = destino
            if destino == TipoDestino.RUTA:
                mov.ruta_nombre = random.choice(rutas).nombre
            else:
                mov.nota_terceros = fake.name()
        
        session.add(mov)
        
        # Commit cada 200 registros para no saturar la RAM
        if i % 200 == 0:
            session.commit()
            print(f"   ... {i} registros procesados")

    session.commit()
    print(f"✅ ¡{n} Movimientos creados exitosamente!")

def main():
    print("==========================================")
    print("      SEEDER DE BASE DE DATOS INVENTARIO  ")
    print("==========================================")
    
    borrar = input("¿Quieres BORRAR todos los datos existentes antes? (s/n): ")
    
    with Session(engine) as session:
        if borrar.lower() == 's':
            print("🗑️  Limpiando base de datos...")
            session.exec(delete(Movimiento))
            session.exec(delete(Semana))
            session.exec(delete(Periodo))
            session.exec(delete(Producto))
            session.exec(delete(Ruta))
            session.commit()
            print("✨ Base de datos limpia.")

        create_rutas(session)
        create_periodos_semanas(session)
        create_productos(session)
        
        cant_input = input("¿Cuántos movimientos generar? (Enter para 2000): ")
        n = int(cant_input) if cant_input.strip() else 2000
            
        create_movimientos(session, n)
        
        print("\n🚀 ¡Todo listo! Ahora tu app tiene datos masivos.")

if __name__ == "__main__":
    main()