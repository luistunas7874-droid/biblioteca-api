import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def cache_falsa(monkeypatch):
    """Reemplaza Redis por un diccionario, para que las pruebas no dependan de él."""
    almacen = {}

    def fake_get(clave):
        return almacen.get(clave)

    def fake_set(clave, valor, ttl=60):
        almacen[clave] = valor

    def fake_invalidar():
        almacen.clear()

    monkeypatch.setattr("app.routers.libros.cache_get", fake_get)
    monkeypatch.setattr("app.routers.libros.cache_set", fake_set)
    monkeypatch.setattr("app.routers.libros.invalidar_ranking", fake_invalidar)
    monkeypatch.setattr("app.routers.reviews.invalidar_ranking", fake_invalidar)


@pytest.fixture(name="client")
def client_fixture():
    """Cliente de pruebas con una base de datos temporal en memoria."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def crear_autor(client, nombre="Gabriel García Márquez"):
    r = client.post("/autores/", json={"nombre": nombre, "pais": "Colombia"})
    assert r.status_code == 201
    return r.json()


def crear_libro(client, autor_id, titulo="Cien años de soledad"):
    r = client.post(
        "/libros/",
        json={"titulo": titulo, "anio": 1967, "genero": "novela", "autor_id": autor_id},
    )
    assert r.status_code == 201
    return r.json()


def crear_review(client, libro_id, calificacion):
    r = client.post(
        "/reviews/",
        json={"calificacion": calificacion, "comentario": "Prueba", "libro_id": libro_id},
    )
    assert r.status_code == 201
    return r.json()


# ---------- AUTORES ----------
def test_crear_y_listar_autores(client):
    autor = crear_autor(client)
    assert autor["id"] == 1

    r = client.get("/autores/")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_autor_con_nombre_muy_corto_da_422(client):
    r = client.post("/autores/", json={"nombre": "A", "pais": "Chile"})
    assert r.status_code == 422


def test_autor_inexistente_da_404(client):
    assert client.get("/autores/99").status_code == 404


def test_actualizar_autor_con_patch(client):
    autor = crear_autor(client)
    r = client.patch(f"/autores/{autor['id']}", json={"pais": "México"})
    assert r.status_code == 200
    assert r.json()["pais"] == "México"
    assert r.json()["nombre"] == "Gabriel García Márquez"


def test_no_se_puede_borrar_autor_con_libros(client):
    autor = crear_autor(client)
    crear_libro(client, autor["id"])
    assert client.delete(f"/autores/{autor['id']}").status_code == 400


# ---------- LIBROS ----------
def test_libro_con_autor_inexistente_da_400(client):
    r = client.post(
        "/libros/",
        json={"titulo": "X", "anio": 2000, "genero": "novela", "autor_id": 99},
    )
    assert r.status_code == 400


def test_libro_con_anio_invalido_da_422(client):
    autor = crear_autor(client)
    r = client.post(
        "/libros/",
        json={"titulo": "X", "anio": 3000, "genero": "novela", "autor_id": autor["id"]},
    )
    assert r.status_code == 422


def test_filtrar_libros_por_genero(client):
    autor = crear_autor(client)
    crear_libro(client, autor["id"])
    r = client.get("/libros/", params={"genero": "poesia"})
    assert r.status_code == 200
    assert r.json() == []


# ---------- REVIEWS ----------
def test_review_con_calificacion_invalida_da_422(client):
    autor = crear_autor(client)
    libro = crear_libro(client, autor["id"])
    r = client.post(
        "/reviews/",
        json={"calificacion": 9, "comentario": "x", "libro_id": libro["id"]},
    )
    assert r.status_code == 422


def test_review_de_libro_inexistente_da_400(client):
    r = client.post("/reviews/", json={"calificacion": 5, "libro_id": 99})
    assert r.status_code == 400


# ---------- RANKING + CACHÉ ----------
def test_ranking_usa_cache_y_se_invalida(client):
    autor = crear_autor(client)
    libro = crear_libro(client, autor["id"])
    crear_review(client, libro["id"], 5)
    crear_review(client, libro["id"], 3)

    primera = client.get("/libros/ranking").json()
    assert primera["origen"] == "base_de_datos"
    assert primera["ranking"][0]["promedio"] == 4.0
    assert primera["ranking"][0]["total_reviews"] == 2

    segunda = client.get("/libros/ranking").json()
    assert segunda["origen"] == "cache"

    crear_review(client, libro["id"], 4)  # esto debe borrar la caché
    tercera = client.get("/libros/ranking").json()
    assert tercera["origen"] == "base_de_datos"
    assert tercera["ranking"][0]["total_reviews"] == 3


# ---------- PORTADAS ----------
def test_subir_portada_valida(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.libros.CARPETA_PORTADAS", tmp_path)
    autor = crear_autor(client)
    libro = crear_libro(client, autor["id"])

    r = client.post(
        f"/libros/{libro['id']}/portada",
        files={"archivo": ("portada.png", b"contenido-falso", "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["portada"].startswith("/static/portadas/")
    assert len(list(tmp_path.iterdir())) == 1


def test_subir_archivo_que_no_es_imagen_da_400(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.libros.CARPETA_PORTADAS", tmp_path)
    autor = crear_autor(client)
    libro = crear_libro(client, autor["id"])

    r = client.post(
        f"/libros/{libro['id']}/portada",
        files={"archivo": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


# ---------- JSON SCHEMA ----------
def test_schema_de_review_tiene_limites(client):
    r = client.get("/schemas/review")
    assert r.status_code == 200
    calificacion = r.json()["properties"]["calificacion"]
    assert calificacion["minimum"] == 1
    assert calificacion["maximum"] == 5


def test_schema_inexistente_da_404(client):
    assert client.get("/schemas/otra-cosa").status_code == 404
