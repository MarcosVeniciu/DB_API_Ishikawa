from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Estrutura genérica de coleção paginada."""

    items: List[T]
    total: int
    limit: int
    offset: int
