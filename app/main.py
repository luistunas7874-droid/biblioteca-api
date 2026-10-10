from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import models
from app.database import crear_tablas
from app.routers import autores, libros, reviews

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas()
    yield


app = FastAPI(title="Biblioteca API", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(autores.router)
app.include_router(libros.router)
app.include_router(reviews.router)


@app.get("/")
def inicio():
    return {"mensaje": "Biblioteca API funcionando"}


@app.get("/catalogo", include_in_schema=False)
def catalogo():
    return FileResponse(BASE_DIR / "static" / "catalogo.html")


@app.get("/schemas/{nombre}", tags=["JSON Schema"])
def obtener_schema(nombre: str):
    esquemas = {
        "autor": models.AutorCreate,
        "libro": models.LibroCreate,
        "review": models.ReviewCreate,
    }
    modelo = esquemas.get(nombre)
    if not modelo:
        raise HTTPException(
            status_code=404,
            detail="Esquema no encontrado. Usa: autor, libro o review",
        )
    return modelo.model_json_schema()