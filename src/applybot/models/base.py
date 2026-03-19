from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from applybot.config import settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, echo=False)
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=_get_engine())
    return _session_factory


def get_session() -> Session:
    return _get_session_factory()()


def init_db() -> None:
    Base.metadata.create_all(bind=_get_engine())
