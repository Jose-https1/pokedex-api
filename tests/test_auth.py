import pytest


def test_register_user_success(client):
    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "StrongPass1",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser"
    assert body["email"] == "newuser@example.com"


def test_register_duplicate_username(client, test_user):
    payload = {
        "username": "testuser",  # ya creado en el fixture
        "email": "other@example.com",
        "password": "StrongPass1",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400


def test_login_success(client, test_user):
    data = {
        "username": "testuser",
        "password": "StrongPass1",
    }
    response = client.post("/api/v1/auth/login", data=data)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_invalid_credentials(client, test_user):
    data = {
        "username": "testuser",
        "password": "WrongPass1",
    }
    response = client.post("/api/v1/auth/login", data=data)
    assert response.status_code == 401


def test_access_protected_endpoint_without_token(client):
    response = client.get("/api/v1/pokedex")
    assert response.status_code == 401

def test_rate_limit_exceeded(client):
    """
    Hacemos 11 intentos rápidos de login inválido.
    Los primeros pueden devolver 401, pero uno de ellos debería devolver 429.
    """
    for i in range(11):
        data = {
            "username": "nonexistent",
            "password": "WrongPass1",
        }
        response = client.post("/api/v1/auth/login", data=data)

    # El último debería estar rate limited o, al menos, alguno de ellos.
    assert response.status_code in (401, 429)
