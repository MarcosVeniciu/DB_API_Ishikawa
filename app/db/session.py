from typing import Any, Dict, Generator
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import Settings, settings


def build_engine_connect_args(cfg: Settings) -> Dict[str, Any]:
    """Constrói connect_args para o driver psycopg conforme ambiente e pooler Supavisor."""
    connect_args: Dict[str, Any] = {}
    if cfg.DB_PREPARE_THRESHOLD is not None:
        connect_args["prepare_threshold"] = cfg.DB_PREPARE_THRESHOLD
    elif "pooler.supabase.com" in cfg.DATABASE_URL or cfg.ENVIRONMENT == "production":
        connect_args["prepare_threshold"] = None
    return connect_args


def create_db_engine(cfg: Settings = settings) -> Engine:
    """Cria a instância do Engine SQLAlchemy com pooling configurado e resiliência."""
    connect_args = build_engine_connect_args(cfg)
    return create_engine(
        cfg.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=cfg.DB_POOL_SIZE,
        max_overflow=cfg.DB_MAX_OVERFLOW,
        pool_timeout=cfg.DB_POOL_TIMEOUT,
        connect_args=connect_args,
        echo=cfg.ENVIRONMENT == "development",
    )


engine = create_db_engine(settings)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency para injeção de sessão do banco de dados com commit/rollback seguro."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
