from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship



# usuarios:

class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    # relaciones
    pokedex_entries: List["PokedexEntry"] = Relationship(back_populates="owner")
    teams: List["Team"] = Relationship(back_populates="trainer")


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserRead(UserBase):
    id: int
    created_at: datetime
    is_active: bool



#   pokedex entries

class PokedexEntryBase(SQLModel):
    pokemon_id: int = Field(index=True)       # ID en PokeAPI
    pokemon_name: str
    pokemon_sprite: str                       # URL de la imagen

    is_captured: bool = False
    favorite: bool = False
    nickname: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)


class PokedexEntry(PokedexEntryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    capture_date: Optional[datetime] = None

    owner: "User" = Relationship(back_populates="pokedex_entries")


class PokedexEntryCreate(PokedexEntryBase):
    pass


class PokedexEntryRead(PokedexEntryBase):
    id: int
    owner_id: int
    created_at: datetime
    capture_date: Optional[datetime]


#equipos:

class TeamBase(SQLModel):
    name: str = Field(max_length=100)
    description: Optional[str] = None


class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trainer_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    trainer: "User" = Relationship(back_populates="teams")
    members: List["TeamMember"] = Relationship(back_populates="team")


class TeamCreate(TeamBase):
    pokemon_ids: List[int] = []   # IDs de PokedexEntry para formar el equipo


class TeamRead(TeamBase):
    id: int
    trainer_id: int
    created_at: datetime


#miembros del equipo

class TeamMemberBase(SQLModel):
    team_id: int
    pokedex_entry_id: int
    position: int = Field(ge=1, le=6)   # posición 1-6


class TeamMember(TeamMemberBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    team: "Team" = Relationship(back_populates="members")


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberRead(TeamMemberBase):
    id: int
