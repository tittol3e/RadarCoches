"""Generación reproducible sin datos personales ni enlaces a anuncios reales."""
import random
from datetime import datetime, timedelta, timezone

from .models import SyntheticAd

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
CATALOG = (
    ("SEAT", "Ibiza", "1.0 TSI", "gasolina"),
    ("Renault", "Clio", "1.5 dCi", "diésel"),
    ("Toyota", "Corolla", "1.8 Hybrid", "híbrido"),
    ("Peugeot", "308", "1.5 BlueHDi", "diésel"),
)


def generate(source: str, number: int, seed: int = 42) -> dict:
    rng = random.Random(f"{seed}:{source}:{number}")
    marca, modelo, version, fuel = rng.choice(CATALOG)
    year = rng.randint(2010, 2025)
    km = max(1000, (2026 - year) * rng.randint(7000, 18000))
    # Valor EXCLUSIVAMENTE ficticio. No representa tasación ni disponibilidad.
    price = max(1500, 26000 - (2026 - year) * 1000 - km // 25)
    stamp = BASE_TIME + timedelta(seconds=number)
    return SyntheticAd(
        id=f"DEMO-{source}-{number:06}", source=source, marca=marca,
        modelo=modelo, version=version, anio=year, kilometros=km,
        precio_centimos=price * 100, combustible=fuel,
        cambio="automático" if fuel == "híbrido" else "manual",
        provincia=rng.choice(("Cádiz", "Sevilla", "Málaga", "Madrid", "Barcelona")),
        publicado=stamp, actualizado=stamp, estado="activo", version_evento=1,
    ).model_dump(mode="json")
