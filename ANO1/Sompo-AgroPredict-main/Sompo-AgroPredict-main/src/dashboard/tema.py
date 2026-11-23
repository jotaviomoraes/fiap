"""Estilos e indicadores de risco da interface de campo."""

from html import escape
from pathlib import Path

import streamlit as st

from agropredict.avaliacao import Avaliacao
from i18n import formatar_numero, t, tr_classe, tr_recomendacao

ESTILOS = Path(__file__).with_name("tema.css")


def aplicar_tema() -> None:
    st.html(ESTILOS)


def status_risco_lateral() -> None:
    risco = st.session_state.get("_agro_risco_operacao")
    if risco is None:
        return

    classe, equipamento = risco
    st.sidebar.html(
        f'<div class="agro-sidebar-risk" data-risk="{escape(classe)}">'
        f'<span class="agro-risk-chip">{escape(t("Risco {classe}", classe=tr_classe(classe)))}</span>'
        f'<span>{escape(equipamento)}</span></div>'
    )


def cartao_risco(avaliacao: Avaliacao) -> None:
    classe = avaliacao.classe_risco
    st.html(
        f'<section class="agro-risk" data-risk="{escape(classe)}" aria-live="polite">'
        '<div class="agro-risk-heading">'
        f'<span class="agro-risk-label">{escape(t("Score de risco"))}</span>'
        f'<span class="agro-risk-chip">{escape(t("Risco {classe}", classe=tr_classe(classe)))}</span>'
        '</div>'
        f'<div class="agro-risk-score">{escape(formatar_numero(avaliacao.score_risco, 1))} <small>/ 100</small></div>'
        f'<p>{escape(tr_recomendacao(avaliacao.recomendacao))}</p>'
        '</section>'
    )
