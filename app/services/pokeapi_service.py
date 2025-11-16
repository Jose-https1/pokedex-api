
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class PokeAPIService:
    """
    Cliente REST para PokeAPI.

    Expone métodos asíncronos para usar en endpoints FastAPI,
    y un método síncrono `sync_get_pokemon` para usar desde
    código síncrono (por ejemplo en el router de Pokédex).
    """

    BASE_URL = "https://pokeapi.co/api/v2"
    SPRITE_BASE_URL = (
        "https://raw.githubusercontent.com/PokeAPI/"
        "sprites/master/sprites/pokemon/other/official-artwork"
    )

    def __init__(self) -> None:
        # Cache muy sencilla en memoria (bonus de la práctica)
        # clave = str(id_or_name).lower()
        self._pokemon_cache: Dict[str, Dict[str, Any]] = {}

    # -----------------------------
    # Helpers internos
    # -----------------------------
    @staticmethod
    def _cache_key(identifier: str | int) -> str:
        return str(identifier).lower()

    @staticmethod
    def _extract_id_from_url(url: str) -> int:
        """
        En muchas respuestas de PokeAPI viene un campo 'url' con
        formato .../pokemon/<id>/. De ahí sacamos el id.
        """
        try:
            return int(url.rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=500,
                detail="Unexpected PokeAPI URL format",
            )

    @classmethod
    def _build_sprite_url(cls, pokemon_id: int) -> str:
        return f"{cls.SPRITE_BASE_URL}/{pokemon_id}.png"

    @classmethod
    def _transform_pokemon(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        De toda la respuesta de PokeAPI nos quedamos con los campos
        que nos interesan para la práctica.
        """
        pokemon_id = payload["id"]
        name = payload["name"]

        sprites = payload.get("sprites", {}) or {}
        sprite = (
            sprites.get("other", {})
            .get("official-artwork", {})
            .get("front_default")
            or sprites.get("front_default")
            or cls._build_sprite_url(pokemon_id)
        )

        types = [t["type"]["name"] for t in payload.get("types", [])]

        stats = [
            {"name": s["stat"]["name"], "base": s["base_stat"]}
            for s in payload.get("stats", [])
        ]

        abilities = [a["ability"]["name"] for a in payload.get("abilities", [])]

        return {
            "id": pokemon_id,
            "name": name,
            "sprite": sprite,
            "types": types,
            "stats": stats,
            "abilities": abilities,
        }

    @classmethod
    def _handle_httpx_error(cls, exc: httpx.HTTPError) -> None:
        """
        Traducimos errores de httpx a HTTPException de FastAPI.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            if status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="Pokemon not found in PokeAPI",
                )
            logger.error(
                "PokeAPI returned status %s for %s",
                status_code,
                exc.request.url,
            )
            raise HTTPException(
                status_code=502,
                detail="Error calling PokeAPI",
            )
        else:
            # Timeout, problemas de red, etc.
            logger.error("Network error calling PokeAPI: %r", exc)
            raise HTTPException(
                status_code=503,
                detail="Error connecting to PokeAPI",
            )

    # -----------------------------
    # Métodos ASÍNCRONOS (para endpoints)
    # -----------------------------
    async def get_pokemon(self, identifier: str | int) -> Dict[str, Any]:
        """
        Obtiene info completa de un Pokémon (stats, tipos, habilidades...).

        Devuelve un dict simplificado:
        {id, name, sprite, types, stats, abilities}
        """
        key = self._cache_key(identifier)
        if key in self._pokemon_cache:
            return self._pokemon_cache[key]

        url = f"{self.BASE_URL}/pokemon/{identifier}"

        logger.info("PokeAPI GET %s", url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_httpx_error(exc)

        payload = response.json()
        pokemon = self._transform_pokemon(payload)
        self._pokemon_cache[key] = pokemon
        # también cacheamos por id (por si nos llaman luego con el número)
        self._pokemon_cache[str(pokemon["id"])] = pokemon

        return pokemon

    async def search_pokemon(
        self,
        name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Lista Pokémon con paginación o búsqueda por nombre.

        - Si `name` viene informado, devuelve solo ese Pokémon (si existe)
          en la misma estructura de siempre.
        - Si no hay `name`, hace GET /pokemon?limit=&offset= y llena la
          lista llamando a get_pokemon(name) para tener tipos y sprite.
        """
        if name:
            pokemon = await self.get_pokemon(name)
            return {
                "count": 1,
                "limit": 1,
                "offset": 0,
                "results": [pokemon],
            }

        url = f"{self.BASE_URL}/pokemon"
        params = {"limit": limit, "offset": offset}

        logger.info("PokeAPI GET %s params=%s", url, params)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_httpx_error(exc)

        data = response.json()
        results = data.get("results", [])
        count = data.get("count", len(results))

        # Pedimos info detallada en paralelo para poder devolver types y sprite
        tasks = [self.get_pokemon(item["name"]) for item in results]
        detailed = await asyncio.gather(*tasks)

        return {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": detailed,
        }

    async def get_pokemon_by_type(self, type_name: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los Pokémon de un tipo concreto.

        Devuelve una lista de {id, name, sprite, types, ...}
        """
        url = f"{self.BASE_URL}/type/{type_name}"

        logger.info("PokeAPI GET %s", url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            self._handle_httpx_error(exc)

        data = response.json()
        pokemon_entries = data.get("pokemon", [])

        # Cada elemento tiene forma {"pokemon": {"name": "...", "url": "..."}, "slot": ...}
        tasks = [
            self.get_pokemon(entry["pokemon"]["name"])
            for entry in pokemon_entries
        ]
        detailed = await asyncio.gather(*tasks)

        return detailed

    # -----------------------------
    # Método SÍNCRONO (usado desde Pokédex)
    # -----------------------------
    @classmethod
    def sync_get_pokemon(cls, identifier: str | int) -> Dict[str, Any]:
        """
        Versión síncrona para usar en código que no es async
        (por ejemplo, en el router de Pokédex).

        Llama a /pokemon/{id_or_name} y devuelve el mismo dict
        que `get_pokemon`.
        """
        url = f"{cls.BASE_URL}/pokemon/{identifier}"

        logger.info("PokeAPI [sync] GET %s", url)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            cls._handle_httpx_error(exc)

        payload = response.json()
        pokemon = cls._transform_pokemon(payload)
        return pokemon
