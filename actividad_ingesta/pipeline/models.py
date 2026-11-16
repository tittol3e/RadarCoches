"""Esquema estricto del dominio DEMO, ajeno al esquema de anuncios reales."""
from datetime import datetime
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SyntheticAd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=60)
    source: Literal["demo_a", "demo_b"]
    synthetic: Literal[True] = True
    marca: str
    modelo: str
    version: str
    anio: int = Field(ge=1886, le=2030)
    kilometros: int = Field(ge=0)
    precio_centimos: int = Field(ge=0)
    combustible: str
    cambio: str
    provincia: str
    publicado: datetime
    actualizado: datetime
    estado: Literal["activo", "retirado"]
    version_evento: int = Field(ge=1)


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=64, max_length=64)
    seq: int = Field(ge=1)
    source: Literal["demo_a", "demo_b"]
    kind: Literal["created", "updated"]
    ad: SyntheticAd

    def validated(self):
        if self.source != self.ad.source:
            raise ValueError("Fuente de evento y anuncio incoherentes")
        payload = json.dumps(self.ad.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        if hashlib.sha256(payload.encode()).hexdigest() != self.event_id:
            raise ValueError("Huella de evento inválida")
        return self
