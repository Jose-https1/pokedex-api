# tests/test_teams_router.py

from typing import Dict

from app.services.pokeapi_service import PokeAPIService


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
    """Mock de PokeAPIService.sync_get_pokemon para no llamar a la API real."""
    def fake_sync_get_pokemon(identifier: int) -> Dict:
        return {
            "id": identifier,
            "name": f"pokemon-{identifier}",
            "sprite": f"https://example.com/{identifier}.png",
            "types": ["electric"],
        }

    monkeypatch.setattr(PokeAPIService, "sync_get_pokemon", staticmethod(fake_sync_get_pokemon))


def _create_pokedex_entry(client, headers, pokemon_id: int):
    payload = {
        "pokemon_id": pokemon_id,
        "is_captured": True,
        "favorite": False,
        "nickname": f"poke-{pokemon_id}",
        "notes": f"nota-{pokemon_id}",
    }
    resp = client.post("/api/v1/pokedex", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def test_teams_crud_and_export(monkeypatch, client):
    """Flujo completo: crear, listar, actualizar y exportar un equipo."""
    _patch_sync_get_pokemon(monkeypatch)
    headers = _get_auth_headers_for_new_user(client, "teams_user")

    # Primero añadimos dos Pokémon a la Pokédex del usuario
    _create_pokedex_entry(client, headers, 1)
    _create_pokedex_entry(client, headers, 2)

    # Crear equipo
    team_payload = {
        "name": "My Team",
        "description": "Equipo de prueba",
        "pokemon_ids": [1, 2],
    }
    resp_create = client.post("/api/v1/teams", json=team_payload, headers=headers)
    assert resp_create.status_code == 201
    team = resp_create.json()
    assert team["name"] == "My Team"
    assert team["pokemon_ids"] == [1, 2]
    team_id = team["id"]

    # Listar equipos
    resp_list = client.get("/api/v1/teams", headers=headers)
    assert resp_list.status_code == 200
    teams = resp_list.json()
    assert any(t["id"] == team_id for t in teams)

    # Actualizar equipo: cambiar nombre y orden de Pokémon
    update_payload = {
        "name": "Updated Team",
        "description": "Descripción modificada",
        "pokemon_ids": [2, 1],
    }
    resp_update = client.put(f"/api/v1/teams/{team_id}", json=update_payload, headers=headers)
    assert resp_update.status_code == 200
    team_updated = resp_update.json()
    assert team_updated["name"] == "Updated Team"
    assert team_updated["pokemon_ids"] == [2, 1]

    # Exportar equipo a PDF
    resp_export = client.get(f"/api/v1/teams/{team_id}/export", headers=headers)
    assert resp_export.status_code == 200
    assert resp_export.headers["content-type"].startswith("application/pdf")
    assert len(resp_export.content) > 100


def test_create_team_with_duplicated_pokemon_fails(monkeypatch, client):
    """No se permite un equipo con Pokémon duplicados."""
    _patch_sync_get_pokemon(monkeypatch)
    headers = _get_auth_headers_for_new_user(client, "teams_dup_user")

    _create_pokedex_entry(client, headers, 1)

    team_payload = {
        "name": "Invalid Team",
        "description": "Con duplicados",
        "pokemon_ids": [1, 1],
    }
    resp = client.post("/api/v1/teams", json=team_payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "duplicated" in data["detail"].lower()


def test_create_team_with_pokemon_not_in_pokedex_fails(monkeypatch, client):
    """Si el Pokémon no está en la Pokédex del usuario, debe fallar."""
    _patch_sync_get_pokemon(monkeypatch)
    headers = _get_auth_headers_for_new_user(client, "teams_missing_pokedex_user")

    # No creamos ninguna entrada de Pokédex
    team_payload = {
        "name": "Invalid Team",
        "description": "Pokemon not in pokedex",
        "pokemon_ids": [999],
    }
    resp = client.post("/api/v1/teams", json=team_payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "is not in your Pokedex" in data["detail"]
