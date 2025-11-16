# app/models.py

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


# =========================
# MODELOS DE BASE DE DATOS
# =========================

class User(SQLModel, table=True):
    """Usuario del sistema."""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=50)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)


class PokedexEntry(SQLModel, table=True):
    """Entrada en la Pokédex de un usuario."""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Relación con el usuario (solo FK)
    owner_id: int = Field(foreign_key="user.id")

    # Datos del Pokémon (de PokeAPI)
    pokemon_id: int = Field(index=True)  # ID en PokeAPI
    pokemon_name: str
    pokemon_sprite: str  # URL de la imagen

    # Datos configurables por el usuario
    is_captured: bool = Field(default=False)
    capture_date: Optional[datetime] = None
    nickname: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    favorite: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Team(SQLModel, table=True):
    """Equipo de batalla (máximo 6 Pokémon)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    trainer_id: int = Field(foreign_key="user.id")
    name: str = Field(max_length=100)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TeamMember(SQLModel, table=True):
    """Relación muchos a muchos entre Team y PokedexEntry."""
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id")
    pokedex_entry_id: int = Field(foreign_key="pokedexentry.id")
    position: int = Field(ge=1, le=6)  # Posición en el equipo (1-6)


# =========================
# SCHEMAS Pydantic (API)
# =========================

class UserBase(SQLModel):
    username: str
    email: str


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


class PokedexEntryBase(SQLModel):
    pokemon_id: int
    nickname: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_captured: bool = False
    favorite: bool = False


class PokedexEntryCreate(PokedexEntryBase):
    pass


class PokedexEntryRead(PokedexEntryBase):
    id: int
    owner_id: int
    pokemon_name: str
    pokemon_sprite: str
    capture_date: Optional[datetime] = None
    created_at: datetime


class PokedexEntryUpdate(SQLModel):
    nickname: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_captured: Optional[bool] = None
    favorite: Optional[bool] = None
    capture_date: Optional[datetime] = None


class PokedexStats(SQLModel):
    total_pokemon: int
    captured: int
    favorites: int
    completion_percentage: float
    most_common_type: Optional[str] = None
    capture_streak_days: int
