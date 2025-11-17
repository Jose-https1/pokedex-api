# tests/test_pokedex_extra.py

from typing import Dict

from app.services.pokeapi_service import PokeAPIService
from app.routers import pokedex as pokedex_router


def _get_auth_headers_for_new_user(client, username: str):
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


def _patch_sync_get_pokemon(monkeypatch):
    """Mock de la versión síncrona usada en /pokedex (add)."""
    def fake_sync_get_pokemon(identifier: int) -> Dict:
        return {
            "id": identifier,
            "name": f"pokemon-{identifier}",
            "sprite": f"https://example.com/{identifier}.png",
            "types": ["electric"],
        }

    monkeypatch.setattr(PokeAPIService, "sync_get_pokemon", staticmethod(fake_sync_get_pokemon))


async def _fake_get_pokemon_for_stats(identifier: int) -> Dict:
    """Mock async para pokeapi_service.get_pokemon dentro de pokedex.py."""
    # Hacemos que 1 y 2 sean electric, 3 sea water por ejemplo
    if identifier in (1, 2):
        types = ["electric"]
    else:
        types = ["water"]
    return {
        "id": identifier,
        "name": f"pokemon-{identifier}",
        "sprite": f"https://example.com/{identifier}.png",
        "types": types,
        "stats": {},
        "abilities": [],
    }


def _create_pokedex_entry(client, headers, pokemon_id: int, is_captured: bool, favorite: bool):
    payload = {
        "pokemon_id": pokemon_id,
        "is_captured": is_captured,
        "favorite": favorite,
        "nickname": f"poke-{pokemon_id}",
        "notes": f"nota-{pokemon_id}",
    }
    resp = client.post("/api/v1/pokedex", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def test_export_pokedex_csv(monkeypatch, client):
    """Comprueba la exportación CSV básica de la Pokédex."""
    _patch_sync_get_pokemon(monkeypatch)
    headers = _get_auth_headers_for_new_user(client, "pokedex_export_user")

    # Creamos un par de entradas en la Pokédex
    _create_pokedex_entry(client, headers, 1, is_captured=True, favorite=False)
    _create_pokedex_entry(client, headers, 2, is_captured=False, favorite=True)

    resp = client.get("/api/v1/pokedex/export", headers=headers)
    assert resp.status_code == 200
    content_type = resp.headers["content-type"]
    assert "text/csv" in content_type

    # El contenido debe incluir cabecera y algún nombre de Pokémon
    csv_text = resp.content.decode("utf-8-sig")
    assert "pokemon_id" in csv_text
    assert "pokemon-1" in csv_text or "pokemon-2" in csv_text


def test_pokedex_stats_and_v2(monkeypatch, client):
    """
    Comprueba:
    - /api/v1/pokedex/stats calcula bien totales, capturados, favoritos y tipo más común
    - /api/v2/pokedex incluye el campo 'types' para cada entrada
    """
    _patch_sync_get_pokemon(monkeypatch)
    headers = _get_auth_headers_for_new_user(client, "pokedex_stats_user")

    # Creamos varias entradas:
    # 1 y 2 capturados, 2 es favorito, 3 no capturado
    _create_pokedex_entry(client, headers, 1, is_captured=True, favorite=False)
    _create_pokedex_entry(client, headers, 2, is_captured=True, favorite=True)
    _create_pokedex_entry(client, headers, 3, is_captured=False, favorite=False)

    # Mock del get_pokemon async que usa stats y v2
    monkeypatch.setattr(
        pokedex_router.pokeapi_service,
        "get_pokemon",
        _fake_get_pokemon_for_stats,
    )

    # Stats
    resp_stats = client.get("/api/v1/pokedex/stats", headers=headers)
    assert resp_stats.status_code == 200
    stats = resp_stats.json()

    # Tenemos exactamente 3 entradas, 2 capturadas y 1 favorita
    assert stats["total_pokemon"] == 3
    assert stats["captured"] == 2
    assert stats["favorites"] == 1
    # La racha de días será >= 1 (todas en el mismo día cuenta como 1)
    assert stats["capture_streak_days"] >= 1
    # Tipo más común según nuestro mock
    assert stats["most_common_type"] == "electric"

    # v2
    resp_v2 = client.get("/api/v2/pokedex", headers=headers)
    assert resp_v2.status_code == 200
    entries_v2 = resp_v2.json()
    # Debe devolver al menos las 3 entradas creadas
    assert len(entries_v2) >= 3
    # Todas las entradas devueltas deben tener 'types'
    assert all("types" in e for e in entries_v2)
