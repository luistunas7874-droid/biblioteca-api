from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


# ---------- AUTOR ----------
class AutorBase(SQLModel):
    nombre: str = Field(min_length=2, max_length=100)
    pais: str = Field(min_length=2, max_length=60)
    biografia: Optional[str] = Field(default=None, max_length=500)


class Autor(AutorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    libros: list["Libro"] = Relationship(back_populates="autor")


class AutorCreate(AutorBase):
    pass


class AutorUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    pais: Optional[str] = Field(default=None, min_length=2, max_length=60)
    biografia: Optional[str] = Field(default=None, max_length=500)


# ---------- LIBRO ----------
class LibroBase(SQLModel):
    titulo: str = Field(min_length=1, max_length=150)
    anio: int = Field(ge=1400, le=2100)
    genero: str = Field(min_length=2, max_length=50)
    autor_id: int = Field(foreign_key="autor.id")


class Libro(LibroBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    portada: Optional[str] = Field(default=None)
    autor: Optional[Autor] = Relationship(back_populates="libros")
    reviews: list["Review"] = Relationship(back_populates="libro")


class LibroCreate(LibroBase):
    pass


class LibroUpdate(SQLModel):
    titulo: Optional[str] = Field(default=None, min_length=1, max_length=150)
    anio: Optional[int] = Field(default=None, ge=1400, le=2100)
    genero: Optional[str] = Field(default=None, min_length=2, max_length=50)
    autor_id: Optional[int] = None


# ---------- REVIEW ----------
class ReviewBase(SQLModel):
    calificacion: int = Field(ge=1, le=5)
    comentario: Optional[str] = Field(default=None, max_length=500)
    libro_id: int = Field(foreign_key="libro.id")


class Review(ReviewBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    libro: Optional[Libro] = Relationship(back_populates="reviews")


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(SQLModel):
    calificacion: Optional[int] = Field(default=None, ge=1, le=5)
    comentario: Optional[str] = Field(default=None, max_length=500)