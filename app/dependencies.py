# app/dependencies.py

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from .database import get_session
from .models import User
from .auth import get_current_user


# Alias de dependencia para la sesión de BD
SessionDep = Annotated[Session, Depends(get_session)]

# Alias de dependencia para el usuario autenticado
CurrentUser = Annotated[User, Depends(get_current_user)]
