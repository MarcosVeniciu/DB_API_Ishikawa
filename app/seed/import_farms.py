"""
Importador idempotente de dados mock (farms.json e consultor padrão).
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Consultant, Producer
from app.db.session import SessionLocal
from app.core.security import hash_password

logger = logging.getLogger("db_api.seed")

DEFAULT_CONSULTANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_CONSULTANT_NAME = "Consultor Educampo"
DEFAULT_CONSULTANT_EMAIL = "consultor@educampo.com"
DEFAULT_CONSULTANT_PASSWORD = "admin123"
DEFAULT_PRODUCER_PASSWORD = "produtor123"
DEFAULT_FARM_NAME = "Fazenda Sem Nome"
MOCK_EMAIL_DOMAIN = "@educampo.mock"


class SeedSummaryDTO(BaseModel):
    """Estatísticas e métricas resultantes da execução de seed de dados.

    Registra a quantidade de consultores inseridos, produtores cadastrados/ignorados,
    total de fazendas processadas e a duração da operação em milissegundos.
    Ref: Obsidian note [[bdd-db-api-seed-hardening]]
    """

    consultants_inserted: int = Field(default=0, ge=0)
    producers_inserted: int = Field(default=0, ge=0)
    producers_skipped: int = Field(default=0, ge=0)
    total_farms_processed: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0.0, ge=0.0)


def load_farms_json(json_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Lê e desserializa o arquivo farms.json."""
    path = Path(json_path)
    if not path.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent.parent
        candidate = base_dir / path
        if candidate.exists():
            path = candidate

    if not path.exists():
        raise FileNotFoundError(f"Arquivo de seed não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_farm_uuid(raw_id: Any) -> uuid.UUID:
    """Extrai UUID determinístico ou aleatório a partir de raw_id."""
    if not raw_id:
        return uuid.uuid4()
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_id))


def _extract_farm_email(item: Dict[str, Any], farm_uuid: uuid.UUID) -> str:
    """Extrai ou deriva e-mail válido para o produtor."""
    raw_email = (
        item.get("email")
        or item.get("dados", {}).get("email")
        or f"{farm_uuid}{MOCK_EMAIL_DOMAIN}"
    )
    return str(raw_email).strip().lower()


def _parse_iso_timestamp(raw_ts: Any) -> datetime:
    """Converte representação ISO ou timestamp bruto para datetime UTC timezone-aware."""
    if not raw_ts:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def parse_farm_item(
    item: Dict[str, Any], consultant_id: uuid.UUID
) -> Dict[str, Any]:
    """Converte e normaliza um item bruto do farms.json para o schema do Producer."""
    farm_uuid = _extract_farm_uuid(item.get("id_fazenda") or item.get("id"))
    nome = str(item.get("nome", DEFAULT_FARM_NAME)).strip()
    email = _extract_farm_email(item, farm_uuid)

    raw_password = item.get("password") or DEFAULT_PRODUCER_PASSWORD
    hashed_password = hash_password(str(raw_password))

    created_at = _parse_iso_timestamp(item.get("created_at") or item.get("data_cadastro"))

    dados = item.get("dados") or {}
    id_fazenda = str(item.get("id_fazenda") or farm_uuid)

    return {
        "id": farm_uuid,
        "email": email,
        "hashed_password": hashed_password,
        "nome": nome,
        "id_fazenda": id_fazenda,
        "dados": dados,
        "consultant_id": consultant_id,
        "created_at": created_at,
        "updated_at": created_at,
        "version": 1,
    }


def seed_default_consultant(db: Session) -> uuid.UUID:
    """Garante a existência do consultor mock padrão de forma idempotente."""
    consultant = (
        db.query(Consultant)
        .filter(
            (Consultant.id == DEFAULT_CONSULTANT_ID)
            | (Consultant.email == DEFAULT_CONSULTANT_EMAIL)
        )
        .first()
    )
    if consultant:
        return consultant.id

    new_consultant = Consultant(
        id=DEFAULT_CONSULTANT_ID,
        nome=DEFAULT_CONSULTANT_NAME,
        email=DEFAULT_CONSULTANT_EMAIL,
        hashed_password=hash_password(DEFAULT_CONSULTANT_PASSWORD),
        version=1,
    )
    db.add(new_consultant)
    db.flush()
    return new_consultant.id


def _insert_producer_idempotent(db: Session, producer_data: Dict[str, Any]) -> bool:
    """Insere registro de produtor com ON CONFLICT DO NOTHING. Retorna True se inserido."""
    stmt = (
        pg_insert(Producer)
        .values(
            id=producer_data["id"],
            email=producer_data["email"],
            hashed_password=producer_data["hashed_password"],
            nome=producer_data["nome"],
            id_fazenda=producer_data["id_fazenda"],
            dados=producer_data["dados"],
            consultant_id=producer_data["consultant_id"],
            created_at=producer_data["created_at"],
            updated_at=producer_data["updated_at"],
            version=producer_data["version"],
        )
        .on_conflict_do_nothing()
        .returning(Producer.id)
    )
    inserted_id = db.execute(stmt).scalar_one_or_none()
    return inserted_id is not None


def run_seed(
    db: Session, json_path: Optional[Union[str, Path]] = None
) -> SeedSummaryDTO:
    """Executa a importação idempotente de consultor e produtores."""
    start_time = time.perf_counter()
    target_path = json_path or settings.SEED_DATA_PATH

    # 1. Garante consultor padrão
    existing_consultant = (
        db.query(Consultant).filter(Consultant.id == DEFAULT_CONSULTANT_ID).first()
    )
    consultant_id = seed_default_consultant(db)
    consultants_created = 0 if existing_consultant else 1

    # 2. Carrega e insere produtores
    raw_farms = load_farms_json(target_path)
    producers_created = 0
    producers_skipped = 0

    for item in raw_farms:
        parsed = parse_farm_item(item, consultant_id)
        if _insert_producer_idempotent(db, parsed):
            producers_created += 1
        else:
            producers_skipped += 1

    db.commit()
    duration_ms = (time.perf_counter() - start_time) * 1000

    summary = SeedSummaryDTO(
        consultants_inserted=consultants_created,
        producers_inserted=producers_created,
        producers_skipped=producers_skipped,
        total_farms_processed=len(raw_farms),
        duration_ms=round(duration_ms, 2),
    )

    logger.info(
        "Seed concluído: %d consultores, %d produtores criados, %d ignorados em %.2f ms",
        summary.consultants_inserted,
        summary.producers_inserted,
        summary.producers_skipped,
        summary.duration_ms,
    )
    return summary


def main() -> None:
    """Entrypoint CLI para execução manual do seed."""
    parser = argparse.ArgumentParser(
        description="Importador de Seed Idempotente DB_API_Ishikawa"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=settings.SEED_DATA_PATH,
        help="Caminho para o arquivo farms.json",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        summary = run_seed(db, json_path=args.path)
        print("\n=== RESUMO DO SEED ===")
        print(summary.model_dump_json(indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
