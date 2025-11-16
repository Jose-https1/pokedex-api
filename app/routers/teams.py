from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from fastapi import Response

from app.database import get_session
from app.dependencies import get_current_user
from app.models import (
    User,
    Team,
    TeamMember,
    PokedexEntry,
    TeamCreate,
    TeamUpdate,
    TeamRead,
)

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

router = APIRouter(
    prefix="/api/v1/teams",
    tags=["teams"],
)


def ensure_team_owner(team: Team, current_user: User) -> None:
    if team.trainer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this team",
        )


def get_team_pokemon_ids_for_user(
    session: Session,
    team_id: int,
) -> List[int]:
    """
    Devuelve la lista de pokemon_id (PokeAPI) de un equipo,
    ordenados por position.
    """
    results = session.exec(
        select(TeamMember, PokedexEntry)
        .join(PokedexEntry, TeamMember.pokedex_entry_id == PokedexEntry.id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.position)
    ).all()

    pokemon_ids: List[int] = []
    for member, pokedex_entry in results:
        pokemon_ids.append(pokedex_entry.pokemon_id)

    return pokemon_ids


@router.post(
    "",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Team",
)
def create_team(
    data: TeamCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Validaciones básicas
    if not data.pokemon_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team must have at least one Pokémon",
        )

    if len(data.pokemon_ids) > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team cannot have more than 6 Pokémon",
        )

    if len(set(data.pokemon_ids)) != len(data.pokemon_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team cannot contain duplicated Pokémon",
        )

    # Para cada pokemon_id (PokeAPI), buscamos la entrada de Pokédex
    # de este usuario. Si alguno no existe, error.
    pokedex_entry_ids: List[int] = []

    for poke_id in data.pokemon_ids:
        entry = session.exec(
            select(PokedexEntry).where(
                PokedexEntry.owner_id == current_user.id,
                PokedexEntry.pokemon_id == poke_id,
            )
        ).first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pokemon with id {poke_id} is not in your Pokedex",
            )

        pokedex_entry_ids.append(entry.id)

    # Creamos el equipo
    team = Team(
        trainer_id=current_user.id,
        name=data.name,
        description=data.description,
    )
    session.add(team)
    session.flush()  # Para obtener team.id antes del commit

    # Creamos los miembros (TeamMember)
    for position, pokedex_entry_id in enumerate(pokedex_entry_ids, start=1):
        member = TeamMember(
            team_id=team.id,
            pokedex_entry_id=pokedex_entry_id,
            position=position,
        )
        session.add(member)

    session.commit()
    session.refresh(team)

    pokemon_ids = get_team_pokemon_ids_for_user(session, team.id)

    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        pokemon_ids=pokemon_ids,
    )


@router.get(
    "",
    response_model=List[TeamRead],
    summary="List Teams",
)
def list_teams(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    teams = session.exec(
        select(Team).where(Team.trainer_id == current_user.id)
    ).all()

    result: List[TeamRead] = []
    for team in teams:
        pokemon_ids = get_team_pokemon_ids_for_user(session, team.id)
        result.append(
            TeamRead(
                id=team.id,
                name=team.name,
                description=team.description,
                created_at=team.created_at,
                pokemon_ids=pokemon_ids,
            )
        )

    return result


@router.put(
    "/{team_id}",
    response_model=TeamRead,
    summary="Update Team",
)
def update_team(
    team_id: int,
    data: TeamUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    ensure_team_owner(team, current_user)

    # Actualizar nombre / descripción si vienen en el body
    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description

    # Si se envía pokemon_ids, se reemplaza la composición del equipo
    if data.pokemon_ids is not None:
        if not data.pokemon_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team must have at least one Pokémon",
            )

        if len(data.pokemon_ids) > 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team cannot have more than 6 Pokémon",
            )

        if len(set(data.pokemon_ids)) != len(data.pokemon_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team cannot contain duplicated Pokémon",
            )

        # Validar de nuevo que todos están en la Pokédex del usuario
        pokedex_entry_ids: List[int] = []
        for poke_id in data.pokemon_ids:
            entry = session.exec(
                select(PokedexEntry).where(
                    PokedexEntry.owner_id == current_user.id,
                    PokedexEntry.pokemon_id == poke_id,
                )
            ).first()

            if not entry:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pokemon with id {poke_id} is not in your Pokedex",
                )

            pokedex_entry_ids.append(entry.id)

        # Borramos los miembros anteriores y creamos los nuevos
        session.exec(
            select(TeamMember).where(TeamMember.team_id == team.id)
        ).all()  # para que genere la query
        session.query(TeamMember).filter(TeamMember.team_id == team.id).delete()  # type: ignore

        for position, pokedex_entry_id in enumerate(pokedex_entry_ids, start=1):
            member = TeamMember(
                team_id=team.id,
                pokedex_entry_id=pokedex_entry_id,
                position=position,
            )
            session.add(member)

    session.add(team)
    session.commit()
    session.refresh(team)

    pokemon_ids = get_team_pokemon_ids_for_user(session, team.id)

    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        pokemon_ids=pokemon_ids,
    )


@router.get(
    "/{team_id}/export",
    summary="Export Team as PDF",
)
def export_team(
    team_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    ensure_team_owner(team, current_user)

    # Obtenemos miembros + entradas de Pokédex
    results = session.exec(
        select(TeamMember, PokedexEntry)
        .join(PokedexEntry, TeamMember.pokedex_entry_id == PokedexEntry.id)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.position)
    ).all()

    # Generar PDF sencillo en memoria
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, f"Team: {team.name}")
    y -= 25

    if team.description:
        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Description: {team.description}")
        y -= 25

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Pokémon:")
    y -= 20

    c.setFont("Helvetica", 12)
    if not results:
        c.drawString(60, y, "(No Pokémon in this team)")
    else:
        for idx, (member, pokedex_entry) in enumerate(results, start=1):
            line = f"{idx}. {pokedex_entry.pokemon_name} (#{pokedex_entry.pokemon_id})"
            c.drawString(60, y, line)
            y -= 18
            if y < 50:
                c.showPage()
                y = height - 50

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="team_{team.id}.pdf"'
        },
    )
