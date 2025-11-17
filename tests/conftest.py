import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.limiter import limiter


# --- Engine de base de datos de PRUEBAS (en memoria, compartido) ---

test_engine = create_engine(
    "sqlite://",  # en memoria, pero con StaticPool para compartir conexión
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def get_test_session():
    """
    Devuelve una sesión ligada al engine de pruebas.
    Esta es la que usará la app gracias al override de dependencias.
    """
    with Session(test_engine) as session:
        yield session


# Sobrescribimos la dependencia global para que la app use la BD de tests
app.dependency_overrides[get_session] = get_test_session


# --- Configuración GLOBAL de tests (una vez por sesión) ---

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """
    Configuración global de la sesión de tests:
    - desactivar rate limiting.
    (La BD se resetea por test en otro fixture).
    """
    # Desactivar rate limiting durante TODOS los tests
    limiter.enabled = False


# --- Resetear BD ANTES de cada test ---

@pytest.fixture(autouse=True)
def reset_db():
    """
    Se ejecuta automáticamente antes de CADA test.
    Deja la BD limpia (sin tablas → tablas creadas de nuevo).
    Así cada test es totalmente independiente.
    """
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)


# --- Cliente de test ---

@pytest.fixture
def client():
    """
    Devuelve un TestClient con la app ya configurada
    (BD de test + rate limiting desactivado).
    """
    return TestClient(app)


# --- Fixtures de usuario y token ---

@pytest.fixture
def test_user(client):
    """
    Crea un usuario de prueba mediante el endpoint de registro.
    Como la BD se resetea en cada test, siempre debe devolver 201.
    """
    payload = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "StrongPass1",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def auth_headers(client, test_user):
    """
    Hace login con el usuario de prueba y devuelve los headers de Authorization.
    """
    data = {
        "username": "testuser",
        "password": "StrongPass1",
    }
    response = client.post("/api/v1/auth/login", data=data)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
