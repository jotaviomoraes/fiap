"""
avaliacao.py
------------
Combina modelo e regras de dominio em uma unica `Avaliacao`.

E a unica funcao que produz score, classe final e recomendacao: o
dashboard, o simulador e a ingestao em lote no Oracle chamam `avaliar`,
o que garante o mesmo score para a mesma entrada em qualquer banco.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .entrada import Leitura
from .modelo import ModeloRisco
from .regras import (
    CLASSES_COM_ALERTA,
    calcular_score_risco,
    categorizar_alerta,
    contar_alertas,
    gerar_recomendacao,
    verificar_max,
)


@dataclass(frozen=True)
class Avaliacao:
    classe_modelo: str
    classe_risco: str
    score_risco: float
    probabilidades: dict[str, float]
    override_aplicado: bool
    motivo_override: str | None
    variaveis_max: list[str]
    variaveis_alerta: list[str]
    recomendacao: str
    versao_modelo: str
    hash_modelo: str
    categoria_alerta: str | None = field(default=None)
    # Variaveis que mais elevaram o score (explicacao local, CA-01.4)
    explicacao: list[dict] = field(default_factory=list)

    @property
    def gera_alerta(self) -> bool:
        return self.classe_risco in CLASSES_COM_ALERTA

    def prob(self, classe: str) -> float:
        return self.probabilidades.get(classe, 0.0)


def avaliar(modelo: ModeloRisco, leitura: Leitura) -> Avaliacao:
    dados = leitura.como_dict()
    classe_modelo, probs, contribuicoes = modelo.prever(leitura)

    em_max, vars_max = verificar_max(dados)
    _, vars_alerta = contar_alertas(dados)

    classe_final = "ALTO" if em_max else classe_modelo
    motivo = f"Variavel(is) no limite maximo: {', '.join(vars_max)}" if em_max else None
    score = calcular_score_risco(probs.keys(), probs.values(), override_alto=em_max)

    return Avaliacao(
        classe_modelo=classe_modelo,
        classe_risco=classe_final,
        score_risco=score,
        probabilidades=probs,
        override_aplicado=em_max,
        motivo_override=motivo,
        variaveis_max=vars_max,
        variaveis_alerta=vars_alerta,
        recomendacao=gerar_recomendacao(dados, classe_final, vars_max),
        versao_modelo=modelo.versao,
        hash_modelo=modelo.hash_arquivo,
        categoria_alerta=(
            categorizar_alerta(vars_max, vars_alerta)
            if classe_final in CLASSES_COM_ALERTA else None
        ),
        explicacao=[c.como_dict() for c in contribuicoes],
    )
