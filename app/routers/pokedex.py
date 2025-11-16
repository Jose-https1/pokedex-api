# app/routers/pokedex.py

from datetime import datetime, timedelta
from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.dependencies import SessionDep, CurrentUser
from app.models import (
    User,
    PokedexEntry,
    PokedexEntryCreate,
    PokedexEntryRead,
    PokedexEntryUpdate,
    PokedexStats,
)
from app.services.pokeapi_service import PokeAPIService

router = APIRouter(
    prefix="/api/v1/pokedex",
    tags=["pokedex"],
)

pokeapi_service = PokeAPIService()


def ensure_owner(entry: PokedexEntry, current_user: User) -> None:
    if entry.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this Pokédex entry",
        )


@router.post(
    "",
    response_model=PokedexEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Pokemon To Pokedex",
)
def add_pokemon_to_pokedex(
    data: PokedexEntryCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    # Comprobar duplicado para este usuario
    statement = select(PokedexEntry).where(
        PokedexEntry.owner_id == current_user.id,
        PokedexEntry.pokemon_id == data.pokemon_id,
    )
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pokemon already in your Pokedex",
        )

    # Validar que el Pokémon existe en PokeAPI y obtener datos
    pokemon_data = PokeAPIService.sync_get_pokemon(data.pokemon_id)

    entry = PokedexEntry(
        owner_id=current_user.id,
        pokemon_id=pokemon_data["id"],
        pokemon_name=pokemon_data["name"],
        pokemon_sprite=pokemon_data["sprite"],
        is_captured=data.is_captured,
        favorite=data.favorite,
        nickname=data.nickname,
        notes=data.notes,
        capture_date=datetime.utcnow() if data.is_captured else None,
    )

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.get(
    "",
    response_model=List[PokedexEntryRead],
    summary="List Pokedex",
)
def list_pokedex(
    session: SessionDep,
    current_user: CurrentUser,
    captured: Optional[bool] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
    sort: str = Query(default="pokemon_id", pattern="^(pokemon_id|capture_date|pokemon_name)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),

):
    statement = select(PokedexEntry).where(PokedexEntry.owner_id == current_user.id)

    if captured is not None:
        statement = statement.where(PokedexEntry.is_captured == captured)
    if favorite is not None:
        statement = statement.where(PokedexEntry.favorite == favorite)

    sort_column = {
        "pokemon_id": PokedexEntry.pokemon_id,
        "capture_date": PokedexEntry.capture_date,
        "pokemon_name": PokedexEntry.pokemon_name,
    }[sort]

    if order == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

    statement = statement.offset(offset).limit(limit)
    entries = session.exec(statement).all()
    return entries


@router.patch(
    "/{entry_id}",
    response_model=PokedexEntryRead,
    summary="Update Pokedex Entry",
)
def update_pokedex_entry(
    entry_id: int,
    data: PokedexEntryUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    entry = session.get(PokedexEntry, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pokedex entry not found",
        )

    ensure_owner(entry, current_user)

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)

    # Si se marca como capturado y no tenía fecha, la ponemos ahora
    if "is_captured" in update_data and entry.is_captured and entry.capture_date is None:
        entry.capture_date = datetime.utcnow()

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Pokedex Entry",
)
def delete_pokedex_entry(
    entry_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    entry = session.get(PokedexEntry, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pokedex entry not found",
        )

    ensure_owner(entry, current_user)

    session.delete(entry)
    session.commit()
    return


@router.get(
    "/stats",
    response_model=PokedexStats,
    summary="Get Pokedex Stats",
)
async def get_pokedex_stats(
    session: SessionDep,
    current_user: CurrentUser,
):
    statement = select(PokedexEntry).where(PokedexEntry.owner_id == current_user.id)
    entries = session.exec(statement).all()

    total = len(entries)
    captured = sum(1 for e in entries if e.is_captured)
    favorites = sum(1 for e in entries if e.favorite)

    if total > 0:
        completion_percentage = round(captured * 100.0 / total, 1)
    else:
        completion_percentage = 0.0

    # Calcular streak de días con capturas (máxima racha)
    capture_dates = sorted(
        {e.capture_date.date() for e in entries if e.capture_date is not None}
    )

    longest_streak = 0
    current_streak = 0
    previous_date: Optional[datetime.date] = None

    for d in capture_dates:
        if previous_date is None:
            current_streak = 1
        else:
            if d == previous_date + timedelta(days=1):
                current_streak += 1
            else:
                current_streak = 1
        previous_date = d
        if current_streak > longest_streak:
            longest_streak = current_streak

    # Calcular tipo más común consultando PokeAPI
    type_counter: Counter[str] = Counter()
    seen_ids = set()

    for e in entries:
        if e.pokemon_id in seen_ids:
            continue
        seen_ids.add(e.pokemon_id)

        pokemon_data = await pokeapi_service.get_pokemon(e.pokemon_id)
        for t in pokemon_data.get("types", []):
            type_counter[t] += 1

    most_common_type: Optional[str] = None
    if type_counter:
        most_common_type = type_counter.most_common(1)[0][0]

    return PokedexStats(
        total_pokemon=total,
        captured=captured,
        favorites=favorites,
        completion_percentage=completion_percentage,
        most_common_type=most_common_type,
        capture_streak_days=longest_streak,
    )
