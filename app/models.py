from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


# =========================
#  Usuarios y Auth
# =========================

class UserBase(SQLModel):
    username: str
    email: str


class User(UserBase, table=True):
    """Usuario del sistema"""
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    # Relaciones
    pokedex_entries: List["PokedexEntry"] = Relationship(back_populates="owner")
    teams: List["Team"] = Relationship(back_populates="trainer")


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    is_active: bool


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    username: Optional[str] = None
    user_id: Optional[int] = None


# =========================
#  Pokedex
# =========================

class PokedexEntryBase(SQLModel):
    pokemon_id: int
    is_captured: bool = False
    nickname: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    favorite: bool = False


class PokedexEntry(PokedexEntryBase, table=True):
    """Entrada en la Pokédex de un usuario"""
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id")

    # Datos del Pokémon (de PokeAPI)
    pokemon_name: str
    pokemon_sprite: str  # URL de la imagen

    # Datos temporales
    capture_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relaciones
    owner: User = Relationship(back_populates="pokedex_entries")


class PokedexEntryCreate(SQLModel):
    pokemon_id: int
    nickname: Optional[str] = None
    notes: Optional[str] = None
    is_captured: bool = False
    favorite: bool = False


class PokedexEntryUpdate(SQLModel):
    nickname: Optional[str] = None
    notes: Optional[str] = None
    is_captured: Optional[bool] = None
    favorite: Optional[bool] = None


class PokedexEntryRead(SQLModel):
    id: int
    owner_id: int
    pokemon_id: int
    pokemon_name: str
    pokemon_sprite: str
    is_captured: bool
    capture_date: Optional[datetime]
    nickname: Optional[str]
    notes: Optional[str]
    favorite: bool
    created_at: datetime


class PokedexStats(SQLModel):
    total_pokemon: int
    captured: int
    favorites: int
    completion_percentage: float
    most_common_type: Optional[str]
    capture_streak_days: int


# =========================
#  Equipos de batalla
# =========================

class TeamBase(SQLModel):
    name: str = Field(max_length=100)
    description: Optional[str] = None


class Team(TeamBase, table=True):
    """Equipo de batalla (máximo 6 Pokémon)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    trainer_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relaciones
    trainer: User = Relationship(back_populates="teams")
    members: List["TeamMember"] = Relationship(back_populates="team")


class TeamMember(SQLModel, table=True):
    """Relación muchos a muchos entre Team y PokedexEntry"""
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id")
    pokedex_entry_id: int = Field(foreign_key="pokedexentry.id")
    position: int = Field(ge=1, le=6)

    # Relaciones
    team: Team = Relationship(back_populates="members")
    pokedex_entry: PokedexEntry = Relationship()


# Schemas para Teams (Pydantic)

class TeamCreate(SQLModel):
    """
    Body de creación de equipo.
    pokemon_ids son IDs de PokeAPI (1, 4, 7, 25...), NO ids de PokedexEntry.
    """
    name: str
    description: Optional[str] = None
    pokemon_ids: List[int]


class TeamUpdate(SQLModel):
    """
    Para actualizar nombre/descripcion y, opcionalmente, la lista de miembros.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    pokemon_ids: Optional[List[int]] = None


class TeamMemberRead(SQLModel):
    id: int
    position: int
    pokedex_entry_id: int
    pokemon_id: int
    pokemon_name: str


class TeamRead(SQLModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    members: List[TeamMemberRead]
