"""
Frota e tendencias (US-02) — gestor, analista e admin.

Visao agregada por equipamento, regiao e tipo de operacao: resumo do
periodo (CA-02.1), ranking (CA-02.2), drilldown com padrao por hora
(CA-02.3) e fatores de risco predominantes (CA-02.4).
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from agropredict.relatorios import Filtros
from ui_comum import COR_SERIE_UNICA, barra_filtros, botao_csv, contexto, cores_para, exigir, tabela

DIMENSOES_ROTULO = {
    "Região": "regiao",
    "Tipo de operação": "status_operacao",
    "Equipamento": "equipamento",
    "Tipo de equipamento": "tipo_equipamento",
}


def _kpis(resumo: dict) -> None:
    total = int(resumo["total"])
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Operações avaliadas", f"{total:,}".replace(",", "."))
    c2.metric("Equipamentos", int(resumo["equipamentos"]))
    c3.metric("Score médio", f"{resumo['score_medio']:.1f}")
    c4.metric("Score máximo", f"{resumo['score_maximo']:.1f}")
    c5.metric("🔴 Risco ALTO", f"{int(resumo['alto'])}", f"{100 * resumo['alto'] / total:.1f}% das operações",
              delta_color="off")
    c6.metric("⏳ Alertas pendentes", int(resumo["alertas_pendentes"]))
    st.caption(
        f"Distribuição: 🟢 BAIXO {int(resumo['baixo'])} · 🟡 MÉDIO {int(resumo['medio'])} · "
        f"🔴 ALTO {int(resumo['alto'])}"
    )


def _aba_ranking(ctx, filtros) -> None:
    ranking = ctx.relatorios.ranking_equipamentos(filtros)
    st.markdown("**Ranking de equipamentos por score médio** (maior risco primeiro)")
    tabela(
        ranking.drop(columns=["id_equipamento"]),
        column_config={
            "score_medio": st.column_config.ProgressColumn("Score médio", min_value=0, max_value=100, format="%.1f"),
            "score_maximo": st.column_config.NumberColumn("Score máx.", format="%.1f"),
            "qtd_alto": st.column_config.NumberColumn("🔴 ALTO"),
            "alertas_pendentes": st.column_config.NumberColumn("⏳ Pendentes"),
        },
    )
    botao_csv(ranking, "ranking_equipamentos")

    st.markdown("---")
    st.markdown("**🔎 Drilldown por equipamento**")
    opcoes = dict(zip(ranking["id_equipamento"], ranking["equipamento"] + " · " + ranking["regiao"]))
    id_equip = st.selectbox("Equipamento", list(opcoes), format_func=opcoes.get, key="frota_drill")
    if id_equip is None:
        return

    historico = ctx.relatorios.historico_equipamento(int(id_equip), filtros)
    filtros_equip = replace(filtros, equipamentos=[int(id_equip)])
    por_hora = ctx.relatorios.score_por_hora(filtros_equip)

    col_serie, col_hora = st.columns(2)
    with col_serie:
        st.caption("Score de cada leitura ao longo do período")
        serie = historico.assign(data_hora=pd.to_datetime(historico["data_hora"])).set_index("data_hora")
        st.line_chart(serie[["score_risco"]].rename(columns={"score_risco": "Score"}), color=COR_SERIE_UNICA,
                      y_label="Score (0–100)")
    with col_hora:
        st.caption("Score médio por hora do dia — padrões temporais")
        st.bar_chart(por_hora.set_index("hora")[["score_medio"]].rename(columns={"score_medio": "Score médio"}),
                     color=COR_SERIE_UNICA, x_label="Hora do dia", y_label="Score médio")
    tabela(historico, height=280)
    botao_csv(historico, f"historico_equip{int(id_equip)}")


def _aba_tendencias(ctx, filtros) -> None:
    rotulo = st.radio("Agrupar por", list(DIMENSOES_ROTULO), horizontal=True, key="frota_dim")
    dimensao = DIMENSOES_ROTULO[rotulo]

    tendencia = ctx.relatorios.tendencia_diaria(filtros, dimensao)
    resumo = ctx.relatorios.resumo_por_dimensao(filtros, dimensao)
    if tendencia.empty:
        st.info("Sem dados no período.")
        return

    # Cor fixa por entidade (independe do filtro) para nao "repintar" series
    todas = sorted(ctx.relatorios.resumo_por_dimensao(Filtros(), dimensao)["grupo"].astype(str))
    colunas = [str(c) for c in tendencia.columns]
    tendencia.columns = colunas
    tendencia.index = pd.to_datetime(tendencia.index)

    st.caption(f"Score médio diário por {rotulo.lower()}")
    st.line_chart(tendencia, color=cores_para(colunas, todas), y_label="Score médio (0–100)")
    tabela(
        resumo.rename(columns={"grupo": rotulo}),
        column_config={
            "score_medio": st.column_config.ProgressColumn("Score médio", min_value=0, max_value=100, format="%.1f"),
            "pct_alto": st.column_config.NumberColumn("% ALTO", format="%.1f%%"),
            "pct_medio": st.column_config.NumberColumn("% MÉDIO", format="%.1f%%"),
        },
    )
    col_a, col_b = st.columns(2)
    with col_a:
        botao_csv(resumo, f"risco_por_{dimensao}", "⬇️ Exportar resumo (CSV)")
    with col_b:
        botao_csv(tendencia.reset_index(), f"tendencia_por_{dimensao}", "⬇️ Exportar série diária (CSV)")


def _aba_fatores(ctx, filtros) -> None:
    cenarios, variaveis = ctx.relatorios.fatores_risco(filtros)
    if cenarios.empty:
        st.info("Nenhuma predição MÉDIO/ALTO no período.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Cenários de risco (recomendação emitida) em predições MÉDIO/ALTO")
        st.bar_chart(cenarios.set_index("cenario")[["total"]].rename(columns={"total": "Ocorrências"}),
                     horizontal=True, color=COR_SERIE_UNICA, sort="-Ocorrências")
    with col2:
        st.caption("Variáveis acima do limiar de alerta nessas predições")
        st.bar_chart(variaveis.set_index("variavel")[["ocorrencias"]].rename(columns={"ocorrencias": "Ocorrências"}),
                     horizontal=True, color=COR_SERIE_UNICA, sort="-Ocorrências")
    tabela(cenarios)
    botao_csv(cenarios, "fatores_risco")


def render() -> None:
    exigir("frota")
    ctx = contexto()
    st.title("🚜 Frota e tendências de risco")
    filtros = barra_filtros("frota")

    resumo = ctx.relatorios.resumo(filtros)
    if not resumo["total"]:
        st.info("Nenhuma predição no período/filtros selecionados. "
                "Para popular a demonstração: `python scripts/simular_frota.py`.")
        return
    _kpis(resumo)

    aba_rank, aba_tend, aba_fat = st.tabs(["🏆 Ranking e drilldown", "📈 Tendências", "🧭 Fatores de risco"])
    with aba_rank:
        _aba_ranking(ctx, filtros)
    with aba_tend:
        _aba_tendencias(ctx, filtros)
    with aba_fat:
        _aba_fatores(ctx, filtros)
