
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from app.models import User
from app.services.pokeapi_service import PokeAPIService

router = APIRouter(
    prefix="/api/v1/pokemon",
    tags=["pokemon"],
)

pokeapi_service = PokeAPIService()


@router.get(
    "/search",
    summary="Search Pokemon",
    description=(
        "Busca Pokémon en PokeAPI.\n\n"
        "- Si se pasa `name`, devuelve solo ese Pokémon.\n"
        "- Si no se pasa `name`, devuelve una lista paginada."
    ),
)
async def search_pokemon(
    name: Optional[str] = Query(
        default=None,
        description="Nombre del Pokémon (opcional)",
        min_length=1,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Número máximo de resultados",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset para paginación",
    ),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Endpoint proxy a PokeAPI:

    - GET /api/v1/pokemon/search?name=pikachu
    - GET /api/v1/pokemon/search?limit=20&offset=0
    """
    return await pokeapi_service.search_pokemon(
        name=name,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id_or_name}",
    summary="Get Pokemon Details",
    description="Obtiene detalles completos de un Pokémon (stats, tipos, habilidades, sprite).",
)
async def get_pokemon_details(
    id_or_name: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Devuelve un dict:

    {
      'id': ...,
      'name': ...,
      'sprite': ...,
      'types': [...],
      'stats': [{'name': ..., 'base': ...}],
      'abilities': [...]
    }
    """
    return await pokeapi_service.get_pokemon(id_or_name)


@router.get(
    "/type/{type_name}",
    summary="Get Pokemon By Type",
    description="Obtiene todos los Pokémon de un tipo concreto (fire, water, grass...).",
)
async def get_pokemon_by_type(
    type_name: str,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Ejemplo: GET /api/v1/pokemon/type/electric
    """
    if not type_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="type_name is required",
        )

    return await pokeapi_service.get_pokemon_by_type(type_name)
