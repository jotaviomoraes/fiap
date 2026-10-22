"""
Manutencao preventiva — tecnico, gestor e admin.

Prioriza equipamentos pelos alertas de categoria mecanica (idade da
maquina e horas de operacao acima do limiar).
"""

from __future__ import annotations

import streamlit as st

from agropredict.relatorios import LIMIAR_MANUTENCAO_ALTA
from ui_comum import COR_SERIE_UNICA, barra_filtros, botao_csv, contexto, exigir, tabela

EMOJI_PRIORIDADE = {"ALTA": "🔴", "MEDIA": "🟡", "BAIXA": "🟢"}


def render() -> None:
    exigir("manutencao")
    ctx = contexto()
    st.title("🔧 Manutenção preventiva")
    filtros = barra_filtros("manut", dias_padrao=30, com_status=False)

    df = ctx.relatorios.manutencao(filtros)
    if df.empty:
        st.info("Nenhuma predição no período selecionado.")
        return

    st.markdown(
        f"**Critério de prioridade:** 🔴 ALTA com {LIMIAR_MANUTENCAO_ALTA}+ alertas mecânicos no período "
        "ou qualquer alerta mecânico ALTO · 🟡 MÉDIA com 1–2 alertas mecânicos · 🟢 BAIXA sem alertas mecânicos. "
        "Alerta mecânico = idade da máquina > 10 anos ou horas de operação > 8 h como fator dominante."
    )

    c1, c2, c3 = st.columns(3)
    for coluna, prioridade in zip((c1, c2, c3), ("ALTA", "MEDIA", "BAIXA")):
        coluna.metric(f"{EMOJI_PRIORIDADE[prioridade]} Prioridade {prioridade}",
                      int((df["prioridade"] == prioridade).sum()))

    tabela(
        df.drop(columns=["id_equipamento"]).assign(
            prioridade=df["prioridade"].map(lambda p: f"{EMOJI_PRIORIDADE[p]} {p}")
        )
    )
    botao_csv(df, "prioridade_manutencao")

    st.caption("Alertas mecânicos por equipamento no período")
    st.bar_chart(
        df.set_index("equipamento")[["alertas_mecanicos"]].rename(columns={"alertas_mecanicos": "Alertas mecânicos"}),
        color=COR_SERIE_UNICA, sort="-Alertas mecânicos",
    )

    mecanicos = ctx.relatorios.listar_alertas(filtros, categorias=["mecanico"], limite=100)
    if not mecanicos.empty:
        st.subheader("Últimos alertas mecânicos")
        tabela(mecanicos[["id_alerta", "data_emissao", "nivel", "equipamento", "regiao", "operador",
                          "mensagem", "acao_tomada"]])
