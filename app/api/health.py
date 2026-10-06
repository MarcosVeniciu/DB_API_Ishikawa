from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db

health_router = APIRouter(prefix="/health", tags=["Health"])


@health_router.get("/live", status_code=status.HTTP_200_OK)
def liveness():
    """Healthcheck simples para validar se a aplicação está em execução."""
    return {"status": "alive"}


@health_router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Healthcheck de prontidão que valida a conectividade ativa com o PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unready", "database": "disconnected", "detail": str(exc)},
        )
