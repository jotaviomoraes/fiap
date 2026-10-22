"""
regras.py
---------
Fonte unica das regras de dominio: limiares, override, score de risco,
recomendacao e criterio de emissao de alertas.

Limiares de ALERTA por variavel (valor > limiar):
  umidade_solo > 30, declividade > 18, chuva_24h > 10,
  temperatura > 38, velocidade > 10, idade_maquina > 10, horas_operacao > 8

Limiares MAXIMO (override imediato para ALTO, independente do modelo):
  umidade_solo >= 45, declividade >= 25, chuva_24h >= 40,
  temperatura >= 45, velocidade >= 20

Criterio de alerta registrado no banco:
  classe final MEDIO -> alerta nivel MEDIO
  classe final ALTO  -> alerta nivel ALTO
"""

from __future__ import annotations

from collections.abc import Iterable

ALERTA = {
    "umidade_solo": 30,
    "declividade": 18,
    "chuva_24h": 10,
    "temperatura": 38,
    "velocidade": 10,
    "idade_maquina": 10,
    "horas_operacao": 8,
}
MAXIMO = {
    "umidade_solo": 45,
    "declividade": 25,
    "chuva_24h": 40,
    "temperatura": 45,
    "velocidade": 20,
}

PESO_RISCO = {
    "BAIXO": 0.0,
    "MEDIO": 50.0,
    "ALTO": 100.0,
}

CLASSES_COM_ALERTA = ("MEDIO", "ALTO")

# Categoria do alerta, usada para direcionar cada perfil:
# mecanico -> tecnico de manutencao; operacional/climatico -> operador e gestor.
CATEGORIA_POR_VARIAVEL = {
    "umidade_solo": "climatico",
    "chuva_24h": "climatico",
    "temperatura": "climatico",
    "declividade": "operacional",
    "velocidade": "operacional",
    "idade_maquina": "mecanico",
    "horas_operacao": "mecanico",
}


def calcular_score_risco(
    classes: Iterable[str],
    probabilidades: Iterable[float],
    override_alto: bool = False,
) -> float:
    """Retorna risco esperado de 0 a 100, e nao a confianca do modelo.

    BAIXO vale 0, MEDIO vale 50 e ALTO vale 100. Quando uma regra critica
    deterministica forca a classe ALTO, o score tambem passa a 100.
    """
    if override_alto:
        return 100.0

    pares = list(zip(classes, probabilidades))
    if not pares:
        raise ValueError("Classes e probabilidades nao podem estar vazias.")

    desconhecidas = [classe for classe, _ in pares if classe not in PESO_RISCO]
    if desconhecidas:
        raise ValueError(f"Classe(s) de risco desconhecida(s): {desconhecidas}")

    score = sum(PESO_RISCO[classe] * float(prob) for classe, prob in pares)
    return round(max(0.0, min(100.0, score)), 2)


def verificar_max(row: dict) -> tuple[bool, list[str]]:
    """Retorna (em_max, lista de variaveis no MAX)."""
    vars_max = [v for v, lim in MAXIMO.items() if row.get(v, 0) >= lim]
    return len(vars_max) > 0, vars_max


def contar_alertas(row: dict) -> tuple[int, list[str]]:
    """Retorna (n_alertas, lista de variaveis em alerta)."""
    vars_alerta = [v for v, lim in ALERTA.items() if row.get(v, 0) > lim]
    return len(vars_alerta), vars_alerta


def gerar_recomendacao(row: dict, classe: str, vars_max: list) -> str:
    if classe == "BAIXO":
        return "Seguir rota atual"
    if "umidade_solo" in vars_max or (row["umidade_solo"] > 70 and row["chuva_24h"] > 20):
        return "Risco de atolamento — evitar areas saturadas"
    if "declividade" in vars_max or (row["velocidade"] > 15 and row["declividade"] > 18):
        return "Atencao a inclinacao — reduzir velocidade imediatamente"
    if "chuva_24h" in vars_max:
        return "Chuva intensa — suspender operacao"
    if "temperatura" in vars_max or (row["temperatura"] > 38 and row["horas_operacao"] > 8):
        return "Pausa obrigatoria — risco de fadiga e superaquecimento"
    if "velocidade" in vars_max:
        return "Velocidade critica — reduzir imediatamente"
    if row["idade_maquina"] > 10 and row["horas_operacao"] > 8:
        return "Verificar equipamento — desgaste elevado"
    if classe == "ALTO":
        return "Interromper operacao"
    return "Reduzir velocidade e monitorar"


def categorizar_alerta(vars_max: list[str], vars_alerta: list[str]) -> str:
    """Categoria dominante: prioriza variaveis no MAX, depois as em alerta."""
    for grupo in (vars_max, vars_alerta):
        categorias = [CATEGORIA_POR_VARIAVEL[v] for v in grupo if v in CATEGORIA_POR_VARIAVEL]
        if categorias:
            # dict.fromkeys preserva a ordem, entao empates sao deterministicos
            return max(dict.fromkeys(categorias), key=categorias.count)
    return "operacional"
