# tests/test_pokemon_router.py

from typing import Dict, Any, List

from app.routers import pokemon as pokemon_router


def _get_auth_headers_for_new_user(client, username: str):
    """Crea un usuario nuevo y devuelve las cabeceras Authorization."""
    register_payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "StrongPass1",
    }
    resp = client.post("/api/v1/auth/register", json=register_payload)
    assert resp.status_code == 201

    login_data = {"username": username, "password": "StrongPass1"}
    resp_login = client.post("/api/v1/auth/login", data=login_data)
    assert resp_login.status_code == 200

    token = resp_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_search_pokemon_endpoint_uses_service(monkeypatch, client):
    """Comprueba que /pokemon/search llama al servicio y devuelve su resultado."""
    async def fake_search_pokemon(name, limit, offset):
        return {
            "count": 1,
            "results": [
                {"index": offset + 1, "name": "pikachu", "url": "https://pokeapi.co/pikachu"}
            ],
        }

    monkeypatch.setattr(
        pokemon_router.pokeapi_service,
        "search_pokemon",
        fake_search_pokemon,
    )

    headers = _get_auth_headers_for_new_user(client, "pokemon_search_user")

    resp = client.get(
        "/api/v1/pokemon/search",
        params={"name": "pika", "limit": 10, "offset": 0},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["name"] == "pikachu"


def test_search_pokemon_requires_auth(client):
    """Sin Authorization debe devolver 401."""
    resp = client.get("/api/v1/pokemon/search")
    assert resp.status_code == 401


def test_get_pokemon_detail(monkeypatch, client):
    """Comprueba el endpoint de detalle /pokemon/{id_or_name}."""
    async def fake_get_pokemon(identifier):
        assert identifier == "25"
        return {
            "id": 25,
            "name": "pikachu",
            "sprite": None,
            "types": ["electric"],
            "stats": {"hp": 35},
            "abilities": ["static"],
        }

    monkeypatch.setattr(
        pokemon_router.pokeapi_service,
        "get_pokemon",
        fake_get_pokemon,
    )

    resp = client.get("/api/v1/pokemon/25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 25
    assert data["name"] == "pikachu"
    assert data["types"] == ["electric"]


def test_get_pokemon_by_type(monkeypatch, client):
    """Comprueba /pokemon/type/{type_name}."""
    async def fake_get_pokemon_by_type(type_name: str):
        assert type_name == "electric"
        return [
            {"name": "pikachu", "url": "https://pokeapi.co/pikachu"},
            {"name": "raichu", "url": "https://pokeapi.co/raichu"},
        ]

    monkeypatch.setattr(
        pokemon_router.pokeapi_service,
        "get_pokemon_by_type",
        fake_get_pokemon_by_type,
    )

    resp = client.get("/api/v1/pokemon/type/electric")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "pikachu"


def test_get_pokemon_card_generates_pdf(monkeypatch, client):
    """Comprueba que /pokemon/{id}/card devuelve un PDF descargable."""
    async def fake_get_pokemon_with_species(identifier):
        assert identifier == "25"
        return {
            "id": 25,
            "name": "pikachu",
            # sprite = None para no hacer httpx.get en el helper del PDF
            "sprite": None,
            "types": ["electric"],
            "stats": {"hp": 35, "attack": 55, "defense": 40, "speed": 90},
            "abilities": ["static"],
            "description": "Pokémon ratón eléctrico.",
        }

    monkeypatch.setattr(
        pokemon_router.pokeapi_service,
        "get_pokemon_with_species",
        fake_get_pokemon_with_species,
    )

    headers = _get_auth_headers_for_new_user(client, "pokemon_card_user")

    resp = client.get("/api/v1/pokemon/25/card", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    content_disp = resp.headers.get("content-disposition", "")
    assert "attachment;" in content_disp
    assert ".pdf" in content_disp
    # El PDF no debería estar vacío
    assert len(resp.content) > 100
