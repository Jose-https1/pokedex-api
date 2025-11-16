# app/services/pokeapi_service.py

from typing import List, Dict, Any, Optional, Union

import httpx
from fastapi import HTTPException, status


class PokeAPIService:
    BASE_URL = "https://pokeapi.co/api/v2"

    # ---------- Helpers internos ----------

    @classmethod
    def _parse_pokemon(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza el Pokémon de PokeAPI a un diccionario simple:
        {
            "id": int,
            "name": str,
            "sprite": str | None,
            "types": List[str]
        }
        Siempre incluye la clave "sprite" para evitar KeyError.
        """
        # Sprite principal (el típico frente)
        sprite: Optional[str] = None

        sprites = data.get("sprites") or {}
        # Intento 1: front_default
        sprite = sprites.get("front_default")

        # Intento 2: official-artwork (por si algún día PokeAPI no tiene front_default)
        if sprite is None:
            other = sprites.get("other") or {}
            official = other.get("official-artwork") or {}
            sprite = official.get("front_default")

        types = [t["type"]["name"] for t in data.get("types", [])]

        return {
            "id": data["id"],
            "name": data["name"],
            "sprite": sprite,  # <-- SIEMPRE existe la clave
            "types": types,
        }

    # ---------- Métodos síncronos (para usar dentro de endpoints síncronos) ----------

    @classmethod
    def sync_get_pokemon(cls, id_or_name: Union[int, str]) -> Dict[str, Any]:
        """
        Versión síncrona para usar en endpoints normales (no async),
        como en add_pokemon_to_pokedex.
        """
        url = f"{cls.BASE_URL}/pokemon/{id_or_name}"

        try:
            resp = httpx.get(url, timeout=10.0)
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error connecting to PokeAPI",
            )

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pokemon not found in PokeAPI",
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error fetching Pokemon from PokeAPI",
            )

        data = resp.json()
        return cls._parse_pokemon(data)

    # ---------- Métodos asíncronos (para endpoints async, ej. stats) ----------

    @classmethod
    async def get_pokemon(cls, id_or_name: Union[int, str]) -> Dict[str, Any]:
        """
        Versión async del get_pokemon, usada por ejemplo en /pokedex/stats
        para calcular el tipo más común.
        """
        url = f"{cls.BASE_URL}/pokemon/{id_or_name}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pokemon {id_or_name} not found in PokeAPI",
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error fetching Pokemon from PokeAPI",
            )

        data = resp.json()
        return cls._parse_pokemon(data)

    @classmethod
    async def search_pokemon(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Búsqueda sencilla por nombre: hace una llamada a PokeAPI y filtra por substring.
        No es súper eficiente pero para la práctica vale.
        """
        # PokeAPI no tiene un endpoint de búsqueda por nombre parcial,
        # así que normalmente se haría algo más complejo.
        # Para la práctica, podemos limitar a los primeros N ids.
        max_id_to_check = 200  # por ejemplo, primeros 200 Pokémon
        query_lower = query.lower()
        results: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for poke_id in range(1, max_id_to_check + 1):
                if len(results) >= limit:
                    break

                resp = await client.get(f"{cls.BASE_URL}/pokemon/{poke_id}")
                if resp.status_code != 200:
                    continue

                data = resp.json()
                name = data["name"]
                if query_lower in name.lower():
                    results.append(cls._parse_pokemon(data))

        return results

    @classmethod
    async def get_pokemon_by_type(cls, type_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtiene Pokémon por tipo (fire, water, grass, etc.).
        """
        url = f"{cls.BASE_URL}/type/{type_name.lower()}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Type '{type_name}' not found in PokeAPI",
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error fetching type info from PokeAPI",
            )

        data = resp.json()
        # Lista de pokémon de ese tipo
        pokemon_entries = data.get("pokemon", [])[:limit]
        results: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for entry in pokemon_entries:
                pokemon_url: str = entry["pokemon"]["url"]
                resp = await client.get(pokemon_url)
                if resp.status_code != 200:
                    continue
                p_data = resp.json()
                results.append(cls._parse_pokemon(p_data))

        return results
