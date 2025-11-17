from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.limiter import limiter
from app.logging_config import logger
from ..dependencies import SessionDep
from ..models import User, UserCreate, UserRead
from ..auth import authenticate_user, create_access_token, get_password_hash
from ..config import settings


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)



@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")  # 5 registros por hora y por IP
def register_user(
    request: Request,
    user_in: UserCreate,
    session: SessionDep,
) -> User:
    """
    Registro de un nuevo usuario.
    - Verifica que username y email no estén ya usados.
    - Guarda la contraseña hasheada en hashed_password.
    """
    # Comprobar username o email repetidos
    statement = select(User).where(
        (User.username == user_in.username) | (User.email == user_in.email)
    )
    existing_user = session.exec(statement).first()
    if existing_user:
        logger.warning(
            "Register failed (duplicate) | username=%s email=%s",
            user_in.username,
            user_in.email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    logger.info("User registered successfully | user_id=%s username=%s", user.id, user.username)
    return user


@router.post("/login")
@limiter.limit("10/minute")  # 10 intentos de login por minuto y por IP
def login_for_access_token(
    request: Request,
    session: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Login usando formulario OAuth2:
    - username
    - password
    Devuelve un access_token JWT.
    """
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        logger.warning(
            "Login failed (bad credentials) | username=%s",
            form_data.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    logger.info("Login successful | user_id=%s username=%s", user.id, user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
