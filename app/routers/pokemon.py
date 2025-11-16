

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from ..auth import get_current_user
from ..models import User
from ..services.pokeapi_service import PokeAPIService

router = APIRouter(
    prefix="/api/v1/pokemon",
    tags=["pokemon"],
)

# Usamos una única instancia del servicio para todo el router
pokeapi_service = PokeAPIService()


@router.get("/search")
async def search_pokemon(
    name: Optional[str] = Query(
        None,
        description="Nombre del Pokémon a buscar (opcional)",
    ),
    limit: int = Query(
        20,
        ge=1,
        le=200,
        description="Número de Pokémon por página (si no se indica name)",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset para la paginación (si no se indica name)",
    ),
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Busca Pokémon en PokeAPI.

    - Si se indica `name`, devuelve solo ese Pokémon (si existe).
    - Si NO se indica `name`, lista Pokémon con paginación usando
      /pokemon?limit=&offset=.

    Requiere autenticación.
    """

    # Caso 1: búsqueda directa por nombre
    if name:
        pokemon = await pokeapi_service.get_pokemon(name.strip().lower())
        return {
            "count": 1,
            "results": [pokemon],
        }

    # Caso 2: listado paginado
    data = await pokeapi_service.search_pokemon(limit=limit, offset=offset)

    # PokeAPI devuelve solo name+url; aquí enriquecemos cada uno con detalles
    results: List[Dict] = []

    for item in data.get("results", []):
        url = item.get("url", "")
        try:
            poke_id = int(url.rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            # Si no podemos sacar el id, lo saltamos
            continue

        details = await pokeapi_service.get_pokemon(poke_id)
        results.append(details)

    return {
        "count": data.get("count", len(results)),
        "results": results,
    }


@router.get("/{id_or_name}")
async def get_pokemon_details(
    id_or_name: str,
    current_user: User = Depends(get_current_user),
) -> Dict:
    """
    Devuelve los detalles completos de un Pokémon (stats, tipos, habilidades,
    sprite...), usando /pokemon/{id_or_name}.

    Requiere autenticación.
    """
    pokemon = await pokeapi_service.get_pokemon(id_or_name)
    return pokemon

@router.get("/type/{type_name}")
async def get_pokemon_by_type(
    type_name: str,
    current_user=Depends(get_current_user),
):
    """
    Obtiene todos los Pokémon de un tipo concreto (fire, water, grass, etc.).
    """
    return await pokeapi_service.get_pokemon_by_type(type_name)
