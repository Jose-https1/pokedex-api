import pytest


def _add_pokemon(client, auth_headers, pokemon_id=1):
    payload = {
        "pokemon_id": pokemon_id,
        "nickname": "bulbi",
        "is_captured": True,
        "favorite": True,
        "notes": "primer intento",
    }
    response = client.post("/api/v1/pokedex", json=payload, headers=auth_headers)
    return response


def test_add_pokemon_to_pokedex(client, auth_headers):
    response = _add_pokemon(client, auth_headers, pokemon_id=1)
    assert response.status_code == 201
    body = response.json()
    assert body["pokemon_id"] == 1
    assert body["is_captured"] is True


def test_add_duplicate_pokemon(client, auth_headers):
    # Primer alta
    r1 = _add_pokemon(client, auth_headers, pokemon_id=25)
    assert r1.status_code == 201

    # Segundo intento -> debe fallar por duplicado
    r2 = _add_pokemon(client, auth_headers, pokemon_id=25)
    assert r2.status_code == 400


def test_get_pokedex_with_filters(client, auth_headers):
    # Aseguramos que haya al menos un registro
    _add_pokemon(client, auth_headers, pokemon_id=4)

    params = {
        "captured": "true",
        "favorite": "true",
        "sort": "pokemon_id",
        "order": "asc",
    }
    response = client.get("/api/v1/pokedex", params=params, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1


def test_update_pokedex_entry(client, auth_headers):
    # Creamos una entrada
    r = _add_pokemon(client, auth_headers, pokemon_id=7)
    entry_id = r.json()["id"]

    payload = {
        "is_captured": True,
        "nickname": "nuevo-nick",
        "favorite": False,
    }
    response = client.patch(f"/api/v1/pokedex/{entry_id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == "nuevo-nick"
    assert body["favorite"] is False


def test_delete_pokedex_entry(client, auth_headers):
    # Creamos una entrada y luego la borramos
    r = _add_pokemon(client, auth_headers, pokemon_id=10)
    entry_id = r.json()["id"]

    delete_resp = client.delete(f"/api/v1/pokedex/{entry_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    # Comprobar que ya no existe
    get_resp = client.patch(
        f"/api/v1/pokedex/{entry_id}", json={"nickname": "x"}, headers=auth_headers
    )
    assert get_resp.status_code == 404
