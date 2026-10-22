"""
entrada.py
----------
Contrato de entrada do modelo: uma `Leitura` so existe se estiver valida.

Toda fonte (GPS, Open-Meteo, sliders, simulador, lote do Oracle) passa
por `Leitura.de_dict`, que rejeita campos ausentes, nao numericos, NaN
ou fisicamente impossiveis antes que qualquer dado chegue ao banco.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

FEATURES_NUMERICAS = [
    "umidade_solo",
    "declividade",
    "chuva_24h",
    "temperatura",
    "velocidade",
    "idade_maquina",
    "horas_operacao",
]
FEATURES = FEATURES_NUMERICAS + ["status_operacao"]

STATUS_VALIDOS = ("Colheita", "Deslocamento", "Manobra")

# Faixas fisicamente plausiveis (nao sao os limiares de risco).
FAIXAS_VALIDAS = {
    "umidade_solo": (0.0, 100.0),
    "declividade": (0.0, 100.0),
    "chuva_24h": (0.0, 500.0),
    "temperatura": (-10.0, 60.0),
    "velocidade": (0.0, 80.0),
    "idade_maquina": (0.0, 60.0),
    "horas_operacao": (0.0, 24.0),
}


class LeituraInvalida(ValueError):
    """Entrada rejeitada; `problemas` lista todos os campos com erro."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("Leitura invalida: " + "; ".join(problemas))


@dataclass(frozen=True)
class Leitura:
    umidade_solo: float
    declividade: float
    chuva_24h: float
    temperatura: float
    velocidade: float
    idade_maquina: float
    horas_operacao: float
    status_operacao: str

    @classmethod
    def de_dict(cls, dados: dict) -> "Leitura":
        problemas: list[str] = []
        valores: dict = {}

        for campo in FEATURES_NUMERICAS:
            bruto = dados.get(campo)
            if bruto is None:
                problemas.append(f"{campo} ausente")
                continue
            try:
                valor = float(bruto)
            except (TypeError, ValueError):
                problemas.append(f"{campo} nao numerico ({bruto!r})")
                continue
            if math.isnan(valor) or math.isinf(valor):
                problemas.append(f"{campo} invalido ({bruto!r})")
                continue
            minimo, maximo = FAIXAS_VALIDAS[campo]
            if not minimo <= valor <= maximo:
                problemas.append(f"{campo}={valor} fora da faixa [{minimo}, {maximo}]")
                continue
            valores[campo] = valor

        status = dados.get("status_operacao")
        if status not in STATUS_VALIDOS:
            problemas.append(f"status_operacao invalido ({status!r})")
        else:
            valores["status_operacao"] = status

        if problemas:
            raise LeituraInvalida(problemas)
        return cls(**valores)

    def como_dict(self) -> dict:
        return asdict(self)
