from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import create_db_and_tables
from app.models import inventory
from fastapi.middleware.cors import CORSMiddleware
# 1. Importar el router
from app.routers import periodos, productos, movimientos, reportes, rutas

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title="Sistema de Inventario",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se pone el dominio real, para dev usa "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 2. Incluir el router en la app
app.include_router(periodos.router)
app.include_router(productos.router)
app.include_router(movimientos.router)
app.include_router(reportes.router)
app.include_router(rutas.router)

@app.get("/")
def read_root():
    return {"mensaje": "API lista y organizada"}