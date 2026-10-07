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


class SeedSummaryDTO(BaseModel):
    """Estatísticas resultantes da execução de seed."""

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


def parse_farm_item(
    item: Dict[str, Any], consultant_id: uuid.UUID
) -> Dict[str, Any]:
    """Converte e normaliza um item bruto do farms.json para o schema do Producer."""
    raw_id = item.get("id_fazenda") or item.get("id")
    if raw_id:
        try:
            farm_uuid = uuid.UUID(str(raw_id))
        except (ValueError, AttributeError):
            farm_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_id))
    else:
        farm_uuid = uuid.uuid4()

    nome = str(item.get("nome", "Fazenda Sem Nome")).strip()
    raw_email = (
        item.get("email")
        or item.get("dados", {}).get("email")
        or f"{farm_uuid}@educampo.mock"
    )
    email = str(raw_email).strip().lower()

    raw_password = item.get("password") or DEFAULT_PRODUCER_PASSWORD
    hashed_password = hash_password(str(raw_password))

    created_at_raw = item.get("created_at") or item.get("data_cadastro")
    if created_at_raw:
        try:
            created_at = datetime.fromisoformat(
                str(created_at_raw).replace("Z", "+00:00")
            )
        except ValueError:
            created_at = datetime.now(timezone.utc)
    else:
        created_at = datetime.now(timezone.utc)

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
        stmt = (
            pg_insert(Producer)
            .values(
                id=parsed["id"],
                email=parsed["email"],
                hashed_password=parsed["hashed_password"],
                nome=parsed["nome"],
                id_fazenda=parsed["id_fazenda"],
                dados=parsed["dados"],
                consultant_id=parsed["consultant_id"],
                created_at=parsed["created_at"],
                updated_at=parsed["updated_at"],
                version=parsed["version"],
            )
            .on_conflict_do_nothing()
            .returning(Producer.id)
        )
        inserted_id = db.execute(stmt).scalar_one_or_none()
        if inserted_id is not None:
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
