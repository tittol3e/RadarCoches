from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .security import canonical_url

Money = Decimal
def now():
    return datetime.now(timezone.utc).isoformat()

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False, validate_default=True)

class Vehicle(Strict):
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str | None = Field(None, max_length=120)
    version: str | None = Field(None, max_length=160)
    engine: str | None = Field(None, max_length=160)
    year: int | None = Field(None, ge=1886, le=date.today().year+1)
    km: int | None = Field(None, ge=0, le=10000000)
    fuel: str | None = Field(None, max_length=40)
    transmission: str | None = Field(None, max_length=40)
    power: float | None = Field(None, ge=0, le=3000)
    province: str | None = Field(None, max_length=80)
    body: str | None = None
    doors: int | None = Field(None, ge=1, le=8)
    environmental_label: str | None = None
    origin: str | None = None
    mechanical_condition: str | None = None
    aesthetic_condition: str | None = None
    itv: str | None = None
    maintenance: str | None = None
    accidents: str | None = None
    modifications: str | None = None
    owners: int | None = Field(None, ge=0, le=100)
    observations: str | None = Field(None, max_length=10000)

class Listing(Vehicle):
    source: str = Field(default='manual', min_length=1, max_length=80)
    external_id: str | None = Field(None, max_length=160)
    url: str | None = Field(None, max_length=2000)
    published_at: datetime | None = None
    last_checked: datetime | None = None
    verification: Literal['unverified', 'user_checked', 'authorized_source'] = 'unverified'
    availability: Literal['unknown', 'available', 'withdrawn', 'sold'] = 'unknown'
    seller_type: Literal['unknown', 'private', 'professional'] = 'unknown'
    price: Money | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    description: str = Field('', max_length=20000)
    declared_condition: str | None = Field(None, max_length=2000)
    damages: list[str] = Field(default_factory=list, max_length=100)
    urgency: bool = False
    favorite: bool = False
    notes: str = Field('', max_length=10000)
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        canonical_url(value)
        return value

    @model_validator(mode='after')
    def checked(self):
        if self.source.lower().startswith(('demo', 'synthetic', 'sintetic')):
            raise ValueError('Datos sintéticos solo en Laboratorio de datos')
        if self.verification != 'unverified' and self.last_checked is None:
            raise ValueError('Indique fecha real de comprobación')
        if self.last_checked and (self.last_checked.tzinfo is None or self.last_checked > datetime.now(timezone.utc)):
            raise ValueError('Comprobación futura inválida')
        return self

class Comparable(Listing):
    url: str = Field(min_length=8, max_length=2000)
    observed_at: datetime
    verified: bool = False
    condition: str | None = None
    equipment: str | None = None
    listing_id: int | None = None

    @model_validator(mode='after')
    def observation(self):
        if self.price is None or self.year is None or self.km is None:
            raise ValueError('Comparable requiere precio, año y kilómetros')
        if self.observed_at.tzinfo is None or self.observed_at > datetime.now(timezone.utc):
            raise ValueError('Fecha de observación debe incluir zona y no ser futura')
        return self

class Cost(Strict):
    category: str = Field(min_length=1, max_length=100)
    amount: Money | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    verified: bool = False

class Calculation(Strict):
    purchase: Money = Field(ge=0, max_digits=12, decimal_places=2)
    resale: Money = Field(ge=0, max_digits=12, decimal_places=2)
    target_profit: Money = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    costs: list[Cost] = Field(default_factory=list, max_length=100)
    tax_rate: Money = Field(default=0, ge=0, le=1)
    tax_base_floor: Money = Field(default=0, ge=0)
    manual_tax: Money | None = Field(None, ge=0)
    transaction_type: Literal['manual', 'private', 'professional', 'business'] = 'manual'
    fiscal_hp: Money | None = Field(None, ge=0)
    province: str = 'Cádiz'
    scenario: Literal['hypothetical', 'verified_inputs'] = 'hypothetical'

class Valuation(Strict):
    vehicle: Vehicle
    comparable_ids: list[int] = Field(default_factory=list, max_length=300)
    costs: list[Cost] = Field(default_factory=list, max_length=100)
    target_profit: Money = Field(default=0, ge=0)
    purchase: Money = Field(default=0, ge=0)
    tax_rate: Money = Field(default=0, ge=0, le=1)
    tax_base_floor: Money = Field(default=0, ge=0)
    discount_pct: Money = Field(default=0, ge=0, le=50)
    opening_discount_pct: Money = Field(default=0, ge=0, le=50)

class Quote(Strict):
    listing_id: int | None = None
    category: Literal['parts', 'labor', 'paint', 'diagnosis', 'other']
    description: str = Field(min_length=1, max_length=4000)
    amount: Money | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    shipping: Money = Field(default=0, ge=0)
    url: str | None = Field(None, max_length=2000)
    observed_at: datetime | None = None
    confirmed: bool = False
    compatibility_verified: bool = False
    compatibility: dict[str, str] = Field(default_factory=dict)
    alternative: Literal['new', 'used', 'repaired'] = 'new'
    supplier: str | None = Field(None, max_length=200)
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        canonical_url(v)
        return v
    @model_validator(mode='after')
    def confirmation(self):
        if self.confirmed and (self.amount is None or self.observed_at is None):
            raise ValueError('Confirmación requiere importe y fecha observados')
        if self.observed_at and (self.observed_at.tzinfo is None or self.observed_at > datetime.now(timezone.utc)):
            raise ValueError('Fecha de presupuesto inválida')
        if self.compatibility_verified and any(not self.compatibility.get(k) for k in ('generation','engine','body','side','doors','oem','evidence')):
            raise ValueError('Compatibilidad requiere generación, motor, carrocería, lado, puertas, OEM y evidencia (o no aplicable justificado)')
        if self.confirmed and self.category == 'parts' and not self.compatibility_verified:
            raise ValueError('Pieza pendiente de compatibilidad no puede ser gasto confirmado')
        return self

STAGES = ['Detectado','Analizado','Contactado','Oferta enviada','Contraoferta','Inspección','Comprado','No comprado','Vendido']
class Operation(Strict):
    listing_id: int
    stage: str = 'Detectado'
    offer: Money | None = Field(None, ge=0)
    response: str = Field('', max_length=10000)
    inspection: str = Field('', max_length=10000)
    planned_costs: list[Cost] = Field(default_factory=list)
    actual_costs: list[Cost] = Field(default_factory=list)
    purchase_price: Money | None = Field(None, ge=0)
    sale_price: Money | None = Field(None, ge=0)
    purchase_date: date | None = None
    sale_date: date | None = None
    expected_margin: Money | None = None
    notes: str = Field('', max_length=10000)
    @model_validator(mode='after')
    def stage_valid(self):
        if self.stage not in STAGES:
            raise ValueError('Etapa inválida')
        if self.stage in ('Comprado', 'Vendido') and (self.purchase_price is None or self.purchase_date is None):
            raise ValueError('Compra requiere precio y fecha')
        if self.stage == 'Vendido' and (self.sale_price is None or self.sale_date is None):
            raise ValueError('Venta requiere precio y fecha')
        if self.sale_date and self.purchase_date and self.sale_date < self.purchase_date:
            raise ValueError('Venta anterior a compra')
        if any(d and d > date.today() for d in (self.purchase_date,self.sale_date)):
            raise ValueError('No se admiten fechas reales futuras')
        if self.stage == 'Vendido' and any(c.amount is None for c in self.actual_costs):
            raise ValueError('No cerrar venta con gastos reales pendientes')
        return self
