from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticResultSaveDTO(BaseModel):
    """Payload de entrada para salvar ou atualizar diagnóstico agronômico e simulação.

    Utilizado em PUT /v1/diagnostic-results/{producer_id}.
    Ref: Obsidian note [[audit-persistencia-resultados]]
    """

    model_config = ConfigDict(extra="forbid")

    input_data: Dict[str, Any] = Field(..., description="Dados brutos de entrada da coleta agronômica")
    diagnostico: Optional[Dict[str, Any]] = Field(None, description="Resultado processado do diagnóstico")
    simulacao: Optional[Dict[str, Any]] = Field(None, description="Simulações e cenários preditivos calculados")


class DiagnosticResultDTO(BaseModel):
    """DTO de saída para resultado de diagnóstico e simulação persistidos.

    Contém a versão atual do registro para suporte a lock otimista (If-Match / RFC 7807).
    Ref: Obsidian note [[audit-persistencia-resultados]]
    """

    model_config = ConfigDict(from_attributes=True)

    producer_id: UUID = Field(..., description="Identificador único do produtor proprietário")
    input_data: Dict[str, Any]
    diagnostico: Optional[Dict[str, Any]] = None
    simulacao: Optional[Dict[str, Any]] = None
    version: int = Field(default=1, description="Versão do registro para controle de concorrência otimista")
    updated_at: datetime = Field(..., description="Carimbo de data/hora UTC da última atualização")
