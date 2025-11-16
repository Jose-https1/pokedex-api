from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.dependencies import get_current_user
from app.models import User
from app.services.pokeapi_service import PokeAPIService

router = APIRouter(
    prefix="/api/v1/pokemon",
    tags=["pokemon"],
)

pokeapi_service = PokeAPIService()


# ---------- Endpoints de búsqueda / detalle ----------


@router.get(
    "/search",
    summary="Buscar Pokémon en PokeAPI",
)
async def search_pokemon_endpoint(
    name: Optional[str] = Query(default=None, description="Nombre (o parte) del Pokémon"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """
    Proxy a PokeAPI para buscar Pokémon con paginación.
    Requiere autenticación.
    """
    return await pokeapi_service.search_pokemon(name=name, limit=limit, offset=offset)


@router.get(
    "/{id_or_name}",
    summary="Obtener detalles de un Pokémon",
)
async def get_pokemon_endpoint(
    id_or_name: str,
):
    """
    Devuelve detalles completos (simplificados) de un Pokémon:
    id, name, sprite, types, stats, abilities.
    """
    return await pokeapi_service.get_pokemon(id_or_name)


@router.get(
    "/type/{type_name}",
    summary="Obtener Pokémon por tipo",
)
async def get_pokemon_by_type_endpoint(
    type_name: str,
):
    """
    Lista Pokémon pertenecientes a un tipo concreto (grass, fire, water, etc.).
    """
    return await pokeapi_service.get_pokemon_by_type(type_name)


# ---------- Helper para generar el PDF ----------


def _generate_pokemon_card_pdf(pokemon: Dict[str, Any]) -> bytes:
    """
    Genera un PDF sencillo con:
    - Sprite (si se puede descargar)
    - Nombre
    - Tipos
    - Stats principales
    - Habilidades
    - Descripción de la especie
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    name = pokemon.get("name", "").title()
    sprite_url = pokemon.get("sprite")
    types = pokemon.get("types", [])
    stats: Dict[str, int] = pokemon.get("stats", {})
    abilities = pokemon.get("abilities", [])
    description = pokemon.get("description") or "Sin descripción disponible."

    # Título
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, height - 60, f"{name}")

    y = height - 100

    # Intentamos dibujar el sprite (si existe URL)
    if sprite_url:
        try:
            resp = httpx.get(sprite_url, timeout=10.0)
            if resp.status_code == 200:
                img_data = io.BytesIO(resp.content)
                img = ImageReader(img_data)
                img_width = 150
                img_height = 150
                c.drawImage(
                    img,
                    40,
                    y - img_height,
                    width=img_width,
                    height=img_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                y = y - img_height - 20
        except Exception:
            # Si falla la imagen, simplemente seguimos sin sprite
            pass

    # Tipos
    c.setFont("Helvetica-Bold", 12)
    c.drawString(220, height - 100, "Tipos:")
    c.setFont("Helvetica", 12)
    c.drawString(270, height - 100, ", ".join(types) or "-")

    # Stats principales
    important_stats = ["hp", "attack", "defense", "speed"]
    c.setFont("Helvetica-Bold", 12)
    c.drawString(220, height - 120, "Stats:")
    c.setFont("Helvetica", 12)
    y_stats = height - 140
    for stat_name in important_stats:
        value = stats.get(stat_name, "-")
        c.drawString(230, y_stats, f"{stat_name.capitalize()}: {value}")
        y_stats -= 15

    # Habilidades
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y - 10, "Habilidades:")
    c.setFont("Helvetica", 12)
    c.drawString(120, y - 10, ", ".join(abilities) or "-")

    # Descripción
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y - 40, "Descripción:")
    c.setFont("Helvetica", 11)

    text_obj = c.beginText()
    text_obj.setTextOrigin(40, y - 60)
    text_obj.setLeading(14)

    # Partimos la descripción en líneas cortas
    max_chars = 90
    for i in range(0, len(description), max_chars):
        text_obj.textLine(description[i : i + max_chars])

    c.drawText(text_obj)

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()


# ---------- Endpoint del PDF/card ----------


@router.get(
    "/{id_or_name}/card",
    summary="Descargar ficha del Pokémon en PDF",
    response_class=Response,
)
async def get_pokemon_card_endpoint(
    id_or_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    Genera un PDF sencillo con datos del Pokémon y lo devuelve como descarga.
    Requiere autenticación.
    """
    pokemon = await pokeapi_service.get_pokemon_with_species(id_or_name)

    pdf_bytes = _generate_pokemon_card_pdf(pokemon)
    filename = f"{pokemon['name']}_card.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
