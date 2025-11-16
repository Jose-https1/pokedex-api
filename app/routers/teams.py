from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import (
    User,
    PokedexEntry,
    Team,
    TeamMember,
    TeamCreate,
    TeamUpdate,
    TeamRead,
    TeamMemberRead,
)

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


def build_team_read(session: Session, team: Team) -> TeamRead:
    """
    Construye el esquema TeamRead a partir de la BD
    (join TeamMember + PokedexEntry).
    """
    statement = (
        select(TeamMember, PokedexEntry)
        .where(
            TeamMember.team_id == team.id,
            TeamMember.pokedex_entry_id == PokedexEntry.id,
        )
        .order_by(TeamMember.position.asc())
    )
    results = session.exec(statement).all()

    members: List[TeamMemberRead] = []
    for tm, entry in results:
        members.append(
            TeamMemberRead(
                id=tm.id,
                position=tm.position,
                pokedex_entry_id=entry.id,
                pokemon_id=entry.pokemon_id,
                pokemon_name=entry.pokemon_name,
            )
        )

    return TeamRead(
        id=team.id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        members=members,
    )


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
    # Validar número de miembros
    if not data.pokemon_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team must have at least 1 Pokémon",
        )

    if len(data.pokemon_ids) > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team cannot have more than 6 Pokémon",
        )

    # Validar que todos los Pokémon están en la Pokédex del usuario
    pokedex_entries: List[PokedexEntry] = []

    for pid in data.pokemon_ids:
        stmt = select(PokedexEntry).where(
            PokedexEntry.owner_id == current_user.id,
            PokedexEntry.pokemon_id == pid,
        )
        entry = session.exec(stmt).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pokemon with id {pid} is not in your Pokedex",
            )
        pokedex_entries.append(entry)

    # Crear el equipo
    team = Team(
        trainer_id=current_user.id,
        name=data.name,
        description=data.description,
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    # Crear miembros
    for position, entry in enumerate(pokedex_entries, start=1):
        member = TeamMember(
            team_id=team.id,
            pokedex_entry_id=entry.id,
            position=position,
        )
        session.add(member)

    session.commit()
    session.refresh(team)

    return build_team_read(session, team)


@router.get(
    "",
    response_model=List[TeamRead],
    summary="List Teams",
)
def list_teams(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Team).where(Team.trainer_id == current_user.id).order_by(Team.created_at.asc())
    teams = session.exec(stmt).all()
    return [build_team_read(session, t) for t in teams]


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
    update_data = data.dict(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        team.name = update_data["name"]
    if "description" in update_data:
        team.description = update_data["description"]

    # Si vienen pokemon_ids, rehacemos los miembros del equipo
    if "pokemon_ids" in update_data and update_data["pokemon_ids"] is not None:
        pokemon_ids = update_data["pokemon_ids"]

        if len(pokemon_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team must have at least 1 Pokémon",
            )
        if len(pokemon_ids) > 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team cannot have more than 6 Pokémon",
            )

        pokedex_entries: List[PokedexEntry] = []
        for pid in pokemon_ids:
            stmt = select(PokedexEntry).where(
                PokedexEntry.owner_id == current_user.id,
                PokedexEntry.pokemon_id == pid,
            )
            entry = session.exec(stmt).first()
            if not entry:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pokemon with id {pid} is not in your Pokedex",
                )
            pokedex_entries.append(entry)

        # Borrar miembros antiguos
        stmt_del = select(TeamMember).where(TeamMember.team_id == team.id)
        old_members = session.exec(stmt_del).all()
        for m in old_members:
            session.delete(m)

        session.commit()

        # Crear los nuevos miembros
        for position, entry in enumerate(pokedex_entries, start=1):
            member = TeamMember(
                team_id=team.id,
                pokedex_entry_id=entry.id,
                position=position,
            )
            session.add(member)

    session.add(team)
    session.commit()
    session.refresh(team)

    return build_team_read(session, team)


@router.get(
    "/{team_id}",
    response_model=TeamRead,
    summary="Get Team Details",
)
def get_team(
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
    return build_team_read(session, team)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Team",
)
def delete_team(
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

    # Borramos primero los miembros
    stmt_members = select(TeamMember).where(TeamMember.team_id == team.id)
    members = session.exec(stmt_members).all()
    for m in members:
        session.delete(m)

    # Borramos el equipo
    session.delete(team)
    session.commit()
    return


@router.get(
    "/{team_id}/export",
    summary="Export Team (placeholder)",
)
async def export_team_placeholder(
    team_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Placeholder para el endpoint de exportación en PDF.

    Más adelante, en otra rama, implementaremos la generación del PDF.
    De momento solo comprobamos permisos y devolvemos 501.
    """
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    ensure_team_owner(team, current_user)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Team export not implemented yet",
    )
