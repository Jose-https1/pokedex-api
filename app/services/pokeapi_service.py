from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import httpx
from fastapi import HTTPException, status

from app.logging_config import logger


class PokeAPIService:
    BASE_URL = "https://pokeapi.co/api/v2"

    # ---------- helpers internos ----------

    @staticmethod
    async def _get(client: httpx.AsyncClient, url: str) -> Dict:
        start = datetime.utcnow()
        try:
            logger.info("PokeAPI request (async) | GET %s", url)
            resp = await client.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            logger.error("PokeAPI network error | url=%s error=%s", url, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error connecting to PokeAPI",
            ) from exc

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "PokeAPI response (async) | GET %s | status=%d | duration=%.3fs",
            url,
            resp.status_code,
            duration,
        )

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pokemon not found",
            )

        if resp.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PokeAPI error",
            )

        return resp.json()

    @staticmethod
    def _get_sync(url: str) -> Dict:
        start = datetime.utcnow()
        try:
            logger.info("PokeAPI request (sync) | GET %s", url)
            resp = httpx.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            logger.error("PokeAPI network error (sync) | url=%s error=%s", url, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error connecting to PokeAPI",
            ) from exc

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "PokeAPI response (sync) | GET %s | status=%d | duration=%.3fs",
            url,
            resp.status_code,
            duration,
        )

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pokemon not found",
            )

        if resp.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PokeAPI error",
            )

        return resp.json()

    # ---------- servicios públicos ----------

    async def get_pokemon(self, identifier: str | int) -> Dict:
        """
        Obtiene información completa de un Pokémon y la transforma
        a un diccionario simplificado.
        """
        url = f"{self.BASE_URL}/pokemon/{identifier}"

        async with httpx.AsyncClient() as client:
            data = await self._get(client, url)

        # Transformar a formato simplificado
        types = [t["type"]["name"] for t in data.get("types", [])]
        stats = {s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])}
        abilities = [a["ability"]["name"] for a in data.get("abilities", [])]

        result = {
            "id": data["id"],
            "name": data["name"],
            "sprite": data["sprites"]["front_default"],
            "types": types,
            "stats": stats,
            "abilities": abilities,
        }

        return result

    async def search_pokemon(
        self,
        name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict:
        """
        Lista Pokémon con paginación. Si name != None, filtra por nombre.
        """
        url = f"{self.BASE_URL}/pokemon?limit={limit}&offset={offset}"

        async with httpx.AsyncClient() as client:
            data = await self._get(client, url)

        results = data.get("results", [])

        if name:
            name_lower = name.lower()
            results = [p for p in results if name_lower in p["name"].lower()]

        simplified = []
        for idx, p in enumerate(results, start=1):
            simplified.append(
                {
                    "index": offset + idx,
                    "name": p["name"],
                    "url": p["url"],
                }
            )

        return {
            "count": len(simplified),
            "results": simplified,
        }

    async def get_pokemon_by_type(self, type_name: str) -> List[Dict]:
        """
        Obtiene todos los Pokémon de un tipo específico.
        """
        url = f"{self.BASE_URL}/type/{type_name}"

        async with httpx.AsyncClient() as client:
            data = await self._get(client, url)

        pokemon_list = data.get("pokemon", [])
        result: List[Dict] = []

        for p in pokemon_list:
            entry = p.get("pokemon", {})
            result.append(
                {
                    "name": entry.get("name"),
                    "url": entry.get("url"),
                }
            )

        return result

    async def get_pokemon_with_species(self, identifier: str | int) -> Dict:
        """
        Igual que get_pokemon, pero añade descripción de la especie.
        """
        async with httpx.AsyncClient() as client:
            pokemon_url = f"{self.BASE_URL}/pokemon/{identifier}"
            pokemon_data = await self._get(client, pokemon_url)

            species_url = pokemon_data["species"]["url"]
            species_data = await self._get(client, species_url)

        # Descripción en español si existe, si no, en inglés, si no, la primera
        flavor_text_entries = species_data.get("flavor_text_entries", [])
        description = None

        for lang in ["es", "en"]:
            for entry in flavor_text_entries:
                if entry.get("language", {}).get("name") == lang:
                    description = (
                        entry.get("flavor_text", "")
                        .replace("\n", " ")
                        .replace("\f", " ")
                    )
                    break
            if description:
                break

        if not description and flavor_text_entries:
            description = (
                flavor_text_entries[0]
                .get("flavor_text", "")
                .replace("\n", " ")
                .replace("\f", " ")
            )

        types = [t["type"]["name"] for t in pokemon_data.get("types", [])]
        stats = {
            s["stat"]["name"]: s["base_stat"]
            for s in pokemon_data.get("stats", [])
        }
        abilities = [a["ability"]["name"] for a in pokemon_data.get("abilities", [])]

        result = {
            "id": pokemon_data["id"],
            "name": pokemon_data["name"],
            "sprite": pokemon_data["sprites"]["front_default"],
            "types": types,
            "stats": stats,
            "abilities": abilities,
            "description": description,
        }

        return result

    # ---------- método síncrono usado en Pokédex ----------

    @staticmethod
    def sync_get_pokemon(identifier: int) -> Dict:
        """
        Versión síncrona para usar desde endpoints sync (Pokedex).
        """
        url = f"{PokeAPIService.BASE_URL}/pokemon/{identifier}"
        data = PokeAPIService._get_sync(url)

        types = [t["type"]["name"] for t in data.get("types", [])]
        result = {
            "id": data["id"],
            "name": data["name"],
            "sprite": data["sprites"]["front_default"],
            "types": types,
        }
        return result
