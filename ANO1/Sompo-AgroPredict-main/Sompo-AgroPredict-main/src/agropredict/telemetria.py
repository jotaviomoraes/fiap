"""
telemetria.py
-------------
Calculo de velocidade a partir de leituras de GPS, sem dependencia de
navegador ou de interface (o componente do navegador fica em
src/dashboard/gps.py).

Duas fontes de velocidade, em ordem de preferencia:
1) `speed_ms` informado pelo chip GPS (m/s), o mais preciso;
2) distancia de Haversine entre a leitura anterior e a atual, dividida
   pelo intervalo de tempo.

Leituras incoerentes (tempo que volta, intervalo nulo, coordenada ausente
ou velocidade fisicamente impossivel) retornam `None`, e quem chama cai
para o valor manual em vez de gravar um dado corrompido.
"""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt

RAIO_TERRA_KM = 6371.0
VELOCIDADE_MAXIMA_KMH = 80.0  # acima disso a leitura e descartada como salto de GPS
LIMIAR_PARADO_KMH = 0.5       # deriva tipica do GPS com o aparelho parado


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia em km entre dois pontos GPS."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return RAIO_TERRA_KM * 2 * atan2(sqrt(a), sqrt(1 - a))


def _coordenadas_validas(p: dict | None) -> bool:
    return bool(p) and all(isinstance(p.get(k), (int, float)) for k in ("lat", "lon", "timestamp")) \
        and -90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180


def calcular_velocidade_kmh(atual: dict | None, anterior: dict | None) -> tuple[float | None, str]:
    """Retorna (velocidade em km/h, origem) com origem em {gps_chip, calculada, indisponivel}."""
    if not _coordenadas_validas(atual):
        return None, "indisponivel"

    speed = atual.get("speed_ms")
    if isinstance(speed, (int, float)) and speed >= 0:
        kmh = speed * 3.6
        return (round(kmh, 1), "gps_chip") if kmh <= VELOCIDADE_MAXIMA_KMH else (None, "indisponivel")

    if not _coordenadas_validas(anterior):
        return None, "indisponivel"  # ainda nao ha 2 pontos para comparar

    dt_h = (atual["timestamp"] - anterior["timestamp"]) / 3600
    if dt_h <= 0:
        return None, "indisponivel"

    kmh = haversine_km(anterior["lat"], anterior["lon"], atual["lat"], atual["lon"]) / dt_h
    if kmh > VELOCIDADE_MAXIMA_KMH:
        return None, "indisponivel"
    return (0.0 if kmh < LIMIAR_PARADO_KMH else round(kmh, 1)), "calculada"
