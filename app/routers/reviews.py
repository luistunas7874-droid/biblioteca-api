from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.cache import invalidar_ranking
from app.database import get_session
from app.models import Libro, Review, ReviewCreate, ReviewUpdate

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/", response_model=list[Review])
def listar_reviews(
    libro_id: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    consulta = select(Review)
    if libro_id:
        consulta = consulta.where(Review.libro_id == libro_id)
    return session.exec(consulta.offset(offset).limit(limit)).all()


@router.get("/{review_id}", response_model=Review)
def obtener_review(review_id: int, session: Session = Depends(get_session)):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review no encontrada")
    return review


@router.post("/", response_model=Review, status_code=201)
def crear_review(datos: ReviewCreate, session: Session = Depends(get_session)):
    if not session.get(Libro, datos.libro_id):
        raise HTTPException(status_code=400, detail="El libro indicado no existe")
    review = Review.model_validate(datos)
    session.add(review)
    session.commit()
    session.refresh(review)
    invalidar_ranking()
    return review


@router.patch("/{review_id}", response_model=Review)
def actualizar_review(
    review_id: int, datos: ReviewUpdate, session: Session = Depends(get_session)
):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review no encontrada")
    review.sqlmodel_update(datos.model_dump(exclude_unset=True))
    session.add(review)
    session.commit()
    session.refresh(review)
    invalidar_ranking()
    return review


@router.delete("/{review_id}", status_code=204)
def borrar_review(review_id: int, session: Session = Depends(get_session)):
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review no encontrada")
    session.delete(review)
    session.commit()
    invalidar_ranking()