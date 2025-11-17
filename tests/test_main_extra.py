#más test para el main, y subir el coverage...
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_has_bearer_auth():
    """
    Comprueba que el esquema OpenAPI personalizado expone BearerAuth.
    Esto ejecuta custom_openapi en app.main.
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    components = schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    assert "BearerAuth" in security_schemes
    bearer = security_schemes["BearerAuth"]
    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
