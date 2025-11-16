
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("pokedex_api.pokeapi")


class PokeAPIService:
    BASE_URL = "https://pokeapi.co/api/v2"

    async def _get(self, client: httpx.AsyncClient, path: str) -> Dict[str, Any]:
        """Helper genérico para hacer peticiones a PokeAPI con manejo de errores."""
        url = f"{self.BASE_URL}{path}"
        logger.info("PokeAPI GET %s", url)

        try:
            resp = await client.get(url, timeout=10.0)
        except httpx.RequestError as exc:
            logger.error("Error comunicando con PokeAPI: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Error comunicando con PokeAPI",
            )

        if resp.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pokémon no encontrado",
            )

        if resp.status_code >= 500:
            logger.error("Error de PokeAPI %s en %s", resp.status_code, url)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error en PokeAPI",
            )

        return resp.json()

    # ---------- Helpers de transformación ----------

    def _extract_sprite(self, data: Dict[str, Any]) -> Optional[str]:
        sprites = data.get("sprites", {}) or {}
        other = sprites.get("other", {}) or {}
        official = other.get("official-artwork", {}) or {}
        sprite = official.get("front_default")
        if sprite:
            return sprite
        return sprites.get("front_default")

    def _extract_stats(self, data: Dict[str, Any]) -> Dict[str, int]:
        return {item["stat"]["name"]: item["base_stat"] for item in data.get("stats", [])}

    def _extract_types(self, data: Dict[str, Any]) -> List[str]:
        return [t["type"]["name"] for t in data.get("types", [])]

    def _extract_abilities(self, data: Dict[str, Any]) -> List[str]:
        return [a["ability"]["name"] for a in data.get("abilities", [])]

    def _extract_description(self, species_data: Dict[str, Any]) -> Optional[str]:
        """
        Saca un flavor_text de la especie, priorizando español 'es', y si no hay, inglés 'en'.
        Limpia saltos de línea raros.
        """
        entries = species_data.get("flavor_text_entries", []) or []

        def pick(lang: str) -> Optional[str]:
            for entry in entries:
                if entry.get("language", {}).get("name") == lang:
                    text = entry.get("flavor_text", "")
                    # limpiar saltos de línea y caracteres raros
                    return text.replace("\n", " ").replace("\f", " ").strip()
            return None

        desc = pick("es") or pick("en")
        return desc

    # ---------- Métodos públicos ----------

    async def get_pokemon(self, identifier: str | int) -> Dict[str, Any]:
        """
        Devuelve información "básica" de un Pokémon, usada por varios endpoints.
        Incluye: id, name, sprite, types, stats, abilities.
        """
        async with httpx.AsyncClient() as client:
            data = await self._get(client, f"/pokemon/{identifier}")

        pokemon = {
            "id": data["id"],
            "name": data["name"],
            "sprite": self._extract_sprite(data),
            "types": self._extract_types(data),
            "stats": self._extract_stats(data),
            "abilities": self._extract_abilities(data),
        }
        return pokemon

    async def get_pokemon_with_species(self, identifier: str | int) -> Dict[str, Any]:
        """
        Igual que get_pokemon, pero añade descripción de la especie (para el PDF/card).
        """
        async with httpx.AsyncClient() as client:
            data = await self._get(client, f"/pokemon/{identifier}")
            species_data = await self._get(client, f"/pokemon-species/{data['id']}")

        pokemon = {
            "id": data["id"],
            "name": data["name"],
            "sprite": self._extract_sprite(data),
            "types": self._extract_types(data),
            "stats": self._extract_stats(data),
            "abilities": self._extract_abilities(data),
            "description": self._extract_description(species_data),
        }
        return pokemon

    async def search_pokemon(
        self,
        name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Lista pokémon con paginación, y opcionalmente filtra por nombre (substring).
        """
        async with httpx.AsyncClient() as client:
            data = await self._get(client, f"/pokemon?limit={limit}&offset={offset}")

        results = []
        for item in data.get("results", []):
            poke_name = item["name"]
            if name and name.lower() not in poke_name.lower():
                continue

            # Intentamos sacar ID del URL
            url: str = item["url"]
            try:
                poke_id = int(url.rstrip("/").split("/")[-1])
            except ValueError:
                poke_id = None

            results.append(
                {
                    "id": poke_id,
                    "name": poke_name,
                }
            )

        return {
            "count": len(results),
            "results": results,
        }

    async def get_pokemon_by_type(self, type_name: str) -> List[Dict[str, Any]]:
        """
        Obtiene pokémon por tipo (solo nombre + id).
        """
        async with httpx.AsyncClient() as client:
            data = await self._get(client, f"/type/{type_name}")

        results: List[Dict[str, Any]] = []
        for item in data.get("pokemon", []):
            poke = item.get("pokemon", {})
            url: str = poke.get("url", "")
            try:
                poke_id = int(url.rstrip("/").split("/")[-1])
            except ValueError:
                poke_id = None

            results.append(
                {
                    "id": poke_id,
                    "name": poke.get("name"),
                }
            )

        return results

    # ---- Helper síncrono que usamos desde endpoints "def" (no async) ----

    @classmethod
    def sync_get_pokemon(cls, identifier: str | int) -> Dict[str, Any]:
        """
        Versión síncrona pensada para usar en endpoints que no son async,
        como el POST de la Pokédex.
        """
        service = cls()
        return asyncio.run(service.get_pokemon(identifier))
