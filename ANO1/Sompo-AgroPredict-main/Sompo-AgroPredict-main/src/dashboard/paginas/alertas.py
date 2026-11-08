"""
Lista de alertas — todos os perfis.

O operador ve apenas os proprios alertas; gestor, tecnico, analista e
admin veem a frota inteira. Os criterios de emissao ficam explicitos
na propria pagina.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from agropredict.regras import ALERTA, CATEGORIA_POR_VARIAVEL, MAXIMO
from i18n import formatar_data, t, tr_acao, tr_categoria, tr_classe, tr_motivo_override, tr_recomendacao, tr_variavel
from ui_comum import EMOJI_ACAO, EMOJI_RISCO, barra_filtros, botao_csv, contexto, exigir, tabela


def criterios() -> None:
    with st.expander(t("📐 Critérios de alerta (como o sistema decide)")):
        st.markdown(t(
            "- **Classe final MÉDIO** → alerta nível 🟡 MÉDIO; **classe final ALTO** → alerta nível 🔴 ALTO.\n"
            "- A classe final é a do modelo, **exceto** quando alguma variável atinge o limite máximo: "
            "nesse caso o override força ALTO e score 100.\n"
            "- A **categoria** é a da variável dominante (no máximo, senão em alerta): "
            "climática, operacional ou mecânica — alertas mecânicos vão para o técnico de manutenção."
        ))
        tabela(pd.DataFrame([
            {
                "variavel": tr_variavel(v),
                "alerta": ALERTA[v],
                "maximo": str(MAXIMO.get(v, "—")),
                "categoria": tr_categoria(CATEGORIA_POR_VARIAVEL[v]),
            }
            for v in ALERTA
        ]), column_config={
            "variavel": st.column_config.Column(t("Variável")),
            "alerta": st.column_config.Column(t("Alerta (>)")),
            "maximo": st.column_config.Column(t("Máximo / override (≥)")),
            "categoria": st.column_config.Column(t("Categoria")),
        })


def render() -> None:
    sessao = exigir("alertas")
    ctx = contexto()
    st.title(t("🚨 Alertas"))
    if sessao.perfil == "operador":
        st.caption(t("Exibindo somente os alertas das suas operações."))

    filtros = barra_filtros("alertas", dias_padrao=7, com_status=False)
    if sessao.perfil == "operador":
        filtros.usuario = sessao.usuario

    c1, c2, c3 = st.columns(3)
    acoes = c1.multiselect(
        t("Situação"), ["PENDENTE", "RESPEITOU", "IGNOROU"], default=["PENDENTE"],
        format_func=lambda a: f"{EMOJI_ACAO[a]} {tr_acao(a)}", placeholder=t("Todas"),
    )
    niveis = c2.multiselect(
        t("Nível"), ["ALTO", "MEDIO"], format_func=lambda n: f"{EMOJI_RISCO[n]} {tr_classe(n)}",
        placeholder=t("Todos"),
    )
    categoria_padrao = ["mecanico"] if sessao.perfil == "tecnico" else []
    categorias = c3.multiselect(
        t("Categoria"), ["climatico", "operacional", "mecanico"], default=categoria_padrao,
        format_func=tr_categoria, placeholder=t("Todas"),
    )

    df = ctx.relatorios.listar_alertas(filtros, acoes, niveis, categorias)
    criterios()

    if df.empty:
        st.info(t("Nenhum alerta para os filtros selecionados."))
        return

    st.caption(t("{n} alerta(s)", n=len(df)))
    exibicao = df.assign(
        nivel=df["nivel"].map(lambda n: f"{EMOJI_RISCO[n]} {tr_classe(n)}"),
        acao_tomada=df["acao_tomada"].map(lambda a: f"{EMOJI_ACAO[a]} {tr_acao(a)}"),
        categoria=df["categoria"].map(tr_categoria),
        mensagem=df["mensagem"].map(tr_recomendacao),
        motivo_override=df["motivo_override"].map(tr_motivo_override),
    )
    tabela(exibicao, height=420, column_config={
        "score_risco": st.column_config.NumberColumn(t("Score"), format="%.1f"),
    })
    botao_csv(df, "alertas")

    pendentes = df[df["acao_tomada"] == "PENDENTE"]
    if not sessao.pode("responder_alerta") or pendentes.empty:
        return

    st.markdown("---")
    st.subheader(t("Registrar resposta a um alerta"))
    with st.form("responder_alerta"):
        rotulos = {
            int(r.id_alerta): f"#{r.id_alerta} · {r.equipamento} · {formatar_data(r.data_emissao, com_hora=True)} · {tr_recomendacao(r.mensagem)}"
            for r in pendentes.itertuples()
        }
        id_alerta = st.selectbox(t("Alerta pendente"), list(rotulos), format_func=rotulos.get)
        acao = st.radio(
            t("Ação tomada"), ["RESPEITOU", "IGNOROU"], horizontal=True,
            format_func=lambda a: f"{EMOJI_ACAO[a]} {tr_acao(a)}",
        )
        observacao = st.text_input(t("Observação (opcional)"), max_chars=500)
        if st.form_submit_button(t("Salvar resposta"), type="primary"):
            if ctx.servico.responder_alerta(id_alerta, acao, sessao.usuario, observacao):
                st.success(t("Resposta registrada no alerta #{id}.", id=id_alerta))
                st.rerun()
            else:
                st.warning(t("Este alerta já havia sido respondido."))
