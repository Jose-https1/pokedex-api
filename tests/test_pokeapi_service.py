import pytest
from fastapi import HTTPException

from app.services.pokeapi_service import PokeAPIService

service = PokeAPIService()


@pytest.mark.asyncio
async def test_pokeapi_service_get_pokemon():
    pokemon = await service.get_pokemon(1)  # Bulbasaur
    assert pokemon["id"] == 1
    assert pokemon["name"] == "bulbasaur"
    assert "types" in pokemon


@pytest.mark.asyncio
async def test_pokeapi_service_handles_404():
    with pytest.raises(HTTPException) as exc:
        await service.get_pokemon(999999)  # ID inventado
    assert exc.value.status_code == 404
