import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlmodel import Session, func, select

from app.cache import cache_get, cache_set, invalidar_ranking
from app.database import get_session
from app.models import Autor, Libro, LibroCreate, LibroUpdate, Review

CARPETA_PORTADAS = Path(__file__).resolve().parent.parent / "static" / "portadas"
TIPOS_PERMITIDOS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB

router = APIRouter(prefix="/libros", tags=["Libros"])


@router.get("/", response_model=list[Libro])
def listar_libros(
    genero: Optional[str] = None,
    autor_id: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    consulta = select(Libro)
    if genero:
        consulta = consulta.where(Libro.genero == genero)
    if autor_id:
        consulta = consulta.where(Libro.autor_id == autor_id)
    return session.exec(consulta.offset(offset).limit(limit)).all()


@router.get("/ranking")
def ranking_libros(
    limite: int = Query(default=5, ge=1, le=20),
    session: Session = Depends(get_session),
):
    clave = f"ranking:{limite}"

    en_cache = cache_get(clave)
    if en_cache is not None:
        return {"origen": "cache", "ranking": en_cache}

    consulta = (
        select(
            Libro.id,
            Libro.titulo,
            func.avg(Review.calificacion).label("promedio"),
            func.count(Review.id).label("total_reviews"),
        )
        .join(Review, Review.libro_id == Libro.id)
        .group_by(Libro.id, Libro.titulo)
        .order_by(func.avg(Review.calificacion).desc(), func.count(Review.id).desc())
        .limit(limite)
    )
    filas = session.exec(consulta).all()
    ranking = [
        {
            "id": fila.id,
            "titulo": fila.titulo,
            "promedio": round(float(fila.promedio), 2),
            "total_reviews": fila.total_reviews,
        }
        for fila in filas
    ]

    cache_set(clave, ranking, ttl=60)
    return {"origen": "base_de_datos", "ranking": ranking}


@router.get("/{libro_id}", response_model=Libro)
def obtener_libro(libro_id: int, session: Session = Depends(get_session)):
    libro = session.get(Libro, libro_id)
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return libro


@router.post("/", response_model=Libro, status_code=201)
def crear_libro(datos: LibroCreate, session: Session = Depends(get_session)):
    if not session.get(Autor, datos.autor_id):
        raise HTTPException(status_code=400, detail="El autor indicado no existe")
    libro = Libro.model_validate(datos)
    session.add(libro)
    session.commit()
    session.refresh(libro)
    return libro


@router.patch("/{libro_id}", response_model=Libro)
def actualizar_libro(
    libro_id: int, datos: LibroUpdate, session: Session = Depends(get_session)
):
    libro = session.get(Libro, libro_id)
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    cambios = datos.model_dump(exclude_unset=True)
    if "autor_id" in cambios and not session.get(Autor, cambios["autor_id"]):
        raise HTTPException(status_code=400, detail="El autor indicado no existe")
    libro.sqlmodel_update(cambios)
    session.add(libro)
    session.commit()
    session.refresh(libro)
    invalidar_ranking()
    return libro


@router.delete("/{libro_id}", status_code=204)
def borrar_libro(libro_id: int, session: Session = Depends(get_session)):
    libro = session.get(Libro, libro_id)
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    for review in libro.reviews:
        session.delete(review)
    session.delete(libro)
    session.commit()
    invalidar_ranking()


@router.post("/{libro_id}/portada", response_model=Libro)
async def subir_portada(
    libro_id: int,
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    libro = session.get(Libro, libro_id)
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")

    extension = TIPOS_PERMITIDOS.get(archivo.content_type)
    if not extension:
        raise HTTPException(
            status_code=400, detail="Solo se permiten imágenes JPG, PNG o WEBP"
        )

    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="La imagen pesa más de 2 MB")

    CARPETA_PORTADAS.mkdir(parents=True, exist_ok=True)

    # Si ya tenía portada, borramos la anterior
    if libro.portada:
        (CARPETA_PORTADAS / Path(libro.portada).name).unlink(missing_ok=True)

    nombre = f"{uuid.uuid4().hex}{extension}"
    (CARPETA_PORTADAS / nombre).write_bytes(contenido)

    libro.portada = f"/static/portadas/{nombre}"
    session.add(libro)
    session.commit()
    session.refresh(libro)
    return libro