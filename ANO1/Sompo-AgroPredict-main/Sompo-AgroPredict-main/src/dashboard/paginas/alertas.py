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
from ui_comum import EMOJI_ACAO, EMOJI_RISCO, barra_filtros, botao_csv, contexto, exigir, tabela


def criterios() -> None:
    with st.expander("📐 Critérios de alerta (como o sistema decide)"):
        st.markdown(
            "- **Classe final MÉDIO** → alerta nível 🟡 MÉDIO; **classe final ALTO** → alerta nível 🔴 ALTO.\n"
            "- A classe final é a do modelo, **exceto** quando alguma variável atinge o limite máximo: "
            "nesse caso o override força ALTO e score 100.\n"
            "- A **categoria** é a da variável dominante (no máximo, senão em alerta): "
            "climática, operacional ou mecânica — alertas mecânicos vão para o técnico de manutenção."
        )
        tabela(pd.DataFrame([
            {"Variável": v, "Alerta (>)": ALERTA[v], "Máximo / override (≥)": str(MAXIMO.get(v, "—")),
             "Categoria": CATEGORIA_POR_VARIAVEL[v]}
            for v in ALERTA
        ]))


def render() -> None:
    sessao = exigir("alertas")
    ctx = contexto()
    st.title("🚨 Alertas")
    if sessao.perfil == "operador":
        st.caption("Exibindo somente os alertas das suas operações.")

    filtros = barra_filtros("alertas", dias_padrao=7, com_status=False)
    if sessao.perfil == "operador":
        filtros.usuario = sessao.usuario

    c1, c2, c3 = st.columns(3)
    acoes = c1.multiselect("Situação", ["PENDENTE", "RESPEITOU", "IGNOROU"], default=["PENDENTE"],
                           format_func=lambda a: f"{EMOJI_ACAO[a]} {a}", placeholder="Todas")
    niveis = c2.multiselect("Nível", ["ALTO", "MEDIO"], format_func=lambda n: f"{EMOJI_RISCO[n]} {n}",
                            placeholder="Todos")
    categoria_padrao = ["mecanico"] if sessao.perfil == "tecnico" else []
    categorias = c3.multiselect("Categoria", ["climatico", "operacional", "mecanico"], default=categoria_padrao,
                                placeholder="Todas")

    df = ctx.relatorios.listar_alertas(filtros, acoes, niveis, categorias)
    criterios()

    if df.empty:
        st.info("Nenhum alerta para os filtros selecionados.")
        return

    st.caption(f"{len(df)} alerta(s)")
    exibicao = df.assign(
        nivel=df["nivel"].map(lambda n: f"{EMOJI_RISCO[n]} {n}"),
        acao_tomada=df["acao_tomada"].map(lambda a: f"{EMOJI_ACAO[a]} {a}"),
    )
    tabela(exibicao, height=420, column_config={
        "score_risco": st.column_config.NumberColumn("Score", format="%.1f"),
    })
    botao_csv(df, "alertas")

    pendentes = df[df["acao_tomada"] == "PENDENTE"]
    if not sessao.pode("responder_alerta") or pendentes.empty:
        return

    st.markdown("---")
    st.subheader("Registrar resposta a um alerta")
    with st.form("responder_alerta"):
        rotulos = {
            int(r.id_alerta): f"#{r.id_alerta} · {r.equipamento} · {r.data_emissao} · {r.mensagem}"
            for r in pendentes.itertuples()
        }
        id_alerta = st.selectbox("Alerta pendente", list(rotulos), format_func=rotulos.get)
        acao = st.radio("Ação tomada", ["RESPEITOU", "IGNOROU"], horizontal=True,
                        format_func=lambda a: f"{EMOJI_ACAO[a]} {a}")
        observacao = st.text_input("Observação (opcional)", max_chars=500)
        if st.form_submit_button("Salvar resposta", type="primary"):
            if ctx.servico.responder_alerta(id_alerta, acao, sessao.usuario, observacao):
                st.success(f"Resposta registrada no alerta #{id_alerta}.")
                st.rerun()
            else:
                st.warning("Este alerta já havia sido respondido.")
