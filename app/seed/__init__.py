"""Módulo de seed idempotente de dados mock do ecossistema Educampo Ishikawa."""

from app.seed.import_farms import run_seed, SeedSummaryDTO

__all__ = ["run_seed", "SeedSummaryDTO"]
