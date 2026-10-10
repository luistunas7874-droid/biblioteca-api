from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Autor, AutorCreate, AutorUpdate

router = APIRouter(prefix="/autores", tags=["Autores"])


@router.get("/", response_model=list[Autor])
def listar_autores(session: Session = Depends(get_session)):
    return session.exec(select(Autor)).all()


@router.get("/{autor_id}", response_model=Autor)
def obtener_autor(autor_id: int, session: Session = Depends(get_session)):
    autor = session.get(Autor, autor_id)
    if not autor:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    return autor


@router.post("/", response_model=Autor, status_code=201)
def crear_autor(datos: AutorCreate, session: Session = Depends(get_session)):
    autor = Autor.model_validate(datos)
    session.add(autor)
    session.commit()
    session.refresh(autor)
    return autor


@router.patch("/{autor_id}", response_model=Autor)
def actualizar_autor(
    autor_id: int, datos: AutorUpdate, session: Session = Depends(get_session)
):
    autor = session.get(Autor, autor_id)
    if not autor:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    autor.sqlmodel_update(datos.model_dump(exclude_unset=True))
    session.add(autor)
    session.commit()
    session.refresh(autor)
    return autor


@router.delete("/{autor_id}", status_code=204)
def borrar_autor(autor_id: int, session: Session = Depends(get_session)):
    autor = session.get(Autor, autor_id)
    if not autor:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    if autor.libros:
        raise HTTPException(
            status_code=400,
            detail="No se puede borrar un autor que tiene libros",
        )
    session.delete(autor)
    session.commit()