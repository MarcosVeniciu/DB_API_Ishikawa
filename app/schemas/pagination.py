from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Estrutura genérica de coleção paginada baseada em limit e offset.

    Encapsula lista tipada de itens, contagem total de registros e metadados de paginação.
    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

    items: List[T]
    total: int
    limit: int
    offset: int
