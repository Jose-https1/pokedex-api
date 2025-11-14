from sqlmodel import create_engine, SQLModel, Session

from .config import settings


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=True,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
