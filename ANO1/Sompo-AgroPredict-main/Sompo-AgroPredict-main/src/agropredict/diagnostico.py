"""Diagnóstico das avaliações registradas, sem carregar ou executar modelos."""

from __future__ import annotations

import json
from pathlib import Path

PASTA_MODELOS = Path(__file__).resolve().parents[1] / "modelo"
CLASSES_RISCO = ("BAIXO", "MEDIO", "ALTO")
RECALL_ALTO_MINIMO = 0.95


def vencedor_risco(candidatos: dict) -> str | None:
    """Repete o critério de seleção do treino, usando somente resultados de CV."""
    elegiveis = {nome: c for nome, c in candidatos.items()
                 if c["recall_alto_cv"] >= RECALL_ALTO_MINIMO}
    return max(elegiveis, key=lambda nome: elegiveis[nome]["f1_macro_cv"], default=None)


def carregar_diagnostico(pasta: Path = PASTA_MODELOS) -> dict:
    """Mantém estágios separados; métrica ausente permanece ausente (nunca zero)."""
    arquivos = {}
    erros = []
    for nome in ("modelo_meta.json", "feedback_bilstm.json", "feedback_bilstm_en.json"):
        try:
            dados = json.loads((pasta / nome).read_text(encoding="utf-8"))
            if not isinstance(dados, dict):
                raise ValueError("metadata must be an object")
            arquivos[nome] = dados
        except (OSError, ValueError):
            erros.append(nome)

    risco = arquivos.get("modelo_meta.json", {})
    modelos = []
    if risco:
        comum = {"familia": "risco", "fonte": "modelo_meta.json", "dataset": risco["dataset"]}
        modelos.append(dict(comum, id="risco_final", nome="Risco atual", etapa="Final",
                            metricas=risco["metricas_teste"], versao=risco["versao"],
                            parametros=risco["hiperparametros"]))
        for i, (nome, candidato) in enumerate(risco.get("candidatos", {}).items()):
            modelos.append(dict(comum, id=f"candidato_{i}", nome=nome, etapa="Candidato",
                                metricas=candidato["teste"], versao=risco["versao"],
                                parametros=candidato["melhores_parametros"]))
        anterior = risco.get("modelo_anterior")
        if anterior:
            modelos.append(dict(comum, id="risco_legado", nome="Risco legado", etapa="Legado",
                                metricas=anterior["teste"], versao=anterior["versao"], parametros={}))
    for idioma, nome in (("pt", "feedback_bilstm.json"), ("en", "feedback_bilstm_en.json")):
        dados = arquivos.get(nome)
        if dados:
            modelos.append({"id": f"sentimento_{idioma}", "nome": f"BiLSTM ({idioma.upper()})",
                            "familia": "sentimento", "etapa": "Final", "fonte": nome,
                            "metricas": dados["metricas"], "dataset": dados["metricas"],
                            "versao": dados["versao"], "parametros": dados["config"],
                            "dominio": dados["dominio"], "origem": dados["fonte"],
                            "data": dados["criado_em"], "epocas": dados["epocas"]})
    return {"risco": risco, "modelos": modelos, "indisponiveis": erros}
