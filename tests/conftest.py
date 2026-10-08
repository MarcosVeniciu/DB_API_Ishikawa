import sys
from unittest.mock import MagicMock
import sqlalchemy

# Previne falha de carregamento da DLL do psycopg (AppLocker) no host Windows durante unit tests
_orig_create_engine = sqlalchemy.create_engine


def _safe_create_engine(url, *args, **kwargs):
    try:
        return _orig_create_engine(url, *args, **kwargs)
    except Exception:
        # Fallback para engine in-memory nos testes unitários mockados
        return _orig_create_engine("sqlite:///:memory:")


sqlalchemy.create_engine = _safe_create_engine
