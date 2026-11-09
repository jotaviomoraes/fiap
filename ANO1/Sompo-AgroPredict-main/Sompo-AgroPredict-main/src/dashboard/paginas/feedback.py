"""Classificação binária de texto no mesmo molde do notebook RNN."""
from __future__ import annotations

import logging
import html
import os
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st
import numpy as np
from threadpoolctl import threadpool_limits

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from agropredict.config import RAIZ_PROJETO
from i18n import t
from ui_comum import exigir


@st.cache_resource
def _analisador(caminho: str, modificado: int, idioma: str):
    from agropredict.feedback_modelo import AnalisadorFeedback
    return AnalisadorFeedback(Path(caminho), idioma)


def grafico_leitura(resultado: dict) -> Figure:
    from matplotlib.figure import Figure

    fig = Figure(figsize=(11, 3.4))
    ax = fig.subplots()
    y = np.asarray(resultado["leitura"])
    x = np.arange(1, len(y) + 1)
    ax.axhline(.5, color="#9CA3AF", ls=":")
    ax.fill_between(x, .5, y, where=y >= .5, color="#16A34A", alpha=.25, interpolate=True)
    ax.fill_between(x, .5, y, where=y < .5, color="#DC2626", alpha=.25, interpolate=True)
    ax.plot(x, y, color="#065A82", lw=2, marker="o", ms=4)
    ax.set_ylim(0, 1)
    ax.set_ylabel(t("Probabilidade de bom"))
    ax.set_title(t("Leitura progressiva: probabilidade após cada palavra"))
    if len(x) <= 40:
        ax.set_xticks(x)
        ax.set_xticklabels(resultado["palavras"], rotation=60, ha="right", fontsize=9)
    else:
        ax.set_xlabel(t("Palavras lidas"))
    ax.grid(alpha=.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def html_raio_x(resultado: dict) -> str:
    importancias = resultado["importancia"]
    limite = max(.02, .15 * max(abs(v) for v in importancias))
    escala = max(1e-6, max(abs(v) for v in importancias))
    partes = []
    for palavra, valor, unk in zip(resultado["palavras"], importancias, resultado["unk"]):
        alpha = min(1., abs(valor) / escala) * .85
        cor = (f"rgba(22,163,74,{alpha:.3f})" if valor > limite else
               f"rgba(220,38,38,{alpha:.3f})" if valor < -limite else "rgba(156,163,175,.12)")
        estilo = "text-decoration:underline dotted;text-underline-offset:4px;" if unk else ""
        partes.append(f'<span title="ΔP={valor:+.4f}" style="background:{cor};{estilo}'
                      f'padding:3px 5px;border-radius:4px;display:inline-block;margin:2px">'
                      f'{html.escape(palavra)}</span>')
    return '<div style="line-height:2.2">' + " ".join(partes) + '</div>'


def diagnostico_tecnico(resultado: dict) -> str:
    top = sorted(zip(resultado["importancia"], resultado["palavras"]),
                 key=lambda item: -abs(item[0]))[:3]
    return "\n".join([
        t("Modelo: {modelo}", modelo=resultado["modelo"]),
        t("Versão: {versao}", versao=resultado["versao_modelo"]),
        t("Acurácia no teste de origem: {acuracia:.1%}", acuracia=resultado["acuracia_teste"]),
        t("Probabilidade bruta de positivo: {probabilidade:.4f}", probabilidade=resultado["prob_bom"]),
        t("Palavras lidas: {lidas} de {total} | fora do vocabulário (<UNK>): {unk}",
          lidas=len(resultado["palavras"]), total=resultado["palavras_total"], unk=sum(resultado["unk"])),
        t("Dispositivo: {dispositivo}", dispositivo=resultado["dispositivo"]),
        t("Palavras mais decisivas: {palavras}",
          palavras=", ".join(f"{palavra} ({valor:+.4f})" for valor, palavra in top)),
    ])


def render() -> None:
    exigir("feedback")
    st.title("o que achou dessa aplicacao ?")
    idiomas = {"pt": t("Português"), "en": t("Inglês")}
    idioma = st.selectbox(t("Idioma do texto"), list(idiomas), format_func=idiomas.get,
                          key="sentimento_idioma")
    st.write(t("Digite um texto no idioma selecionado. A rede RNN/LSTM classifica o sentimento como bom ou ruim."))
    nome = "feedback_bilstm.pt" if idioma == "pt" else "feedback_bilstm_en.pt"
    variavel = "FEEDBACK_MODELO" if idioma == "pt" else "FEEDBACK_MODELO_EN"
    caminho = Path(os.getenv(variavel, RAIZ_PROJETO / "src/modelo" / nome))
    try:
        modelo = _analisador(str(caminho), caminho.stat().st_mtime_ns, idioma) if caminho.is_file() else None
    except Exception:
        logging.getLogger(__name__).exception("Análise de sentimento indisponível")
        modelo = None
    texto = st.text_area(t("Texto para analisar"), max_chars=3000, height=140,
                         placeholder=("Ex.: gostei muito do projeto, é excelente e fácil de usar." if idioma == "pt"
                                      else "E.g.: I really liked this application, it is excellent and easy to use."),
                         key="sentimento_texto")
    if modelo is None:
        st.error(t("Modelo de sentimento indisponível. Verifique a instalação do PyTorch e os pesos do modelo."))
    anterior = st.session_state.get("sentimento_resultado")
    if anterior and (len(anterior) != 3 or anterior[:2] != (texto, idioma)):
        st.session_state.pop("sentimento_resultado", None)
    elif anterior and "importancia" not in anterior[2]:
        st.session_state.pop("sentimento_resultado", None)
    if st.button(t("Analisar sentimento"), type="primary", disabled=modelo is None):
        st.session_state.pop("sentimento_resultado", None)
        if not texto.strip():
            st.warning(t("Digite um texto para analisar."))
        else:
            try:
                with threadpool_limits(limits=1):
                    resultado = modelo.classificar(texto)
            except ValueError:
                st.warning(t("Digite um texto para analisar."))
            except Exception:
                logging.getLogger(__name__).exception("Falha ao classificar texto")
                st.error(t("Não foi possível analisar o texto. Tente novamente."))
            else:
                st.session_state["sentimento_resultado"] = (texto, idioma, resultado)
    st.caption(t("Modelos treinados em avaliações B2W (português) e IMDB (inglês). A classificação pode errar; as probabilidades não são confiança calibrada."))
    anterior = st.session_state.get("sentimento_resultado")
    if anterior and anterior[:2] == (texto, idioma) and modelo is not None:
        resultado = anterior[2]
        bom, ruim = resultado["prob_bom"], resultado["prob_ruim"]
        if resultado["classificacao"] == "BOM":
            st.success(t("BOM — sentimento positivo"))
        else:
            st.error(t("RUIM — sentimento negativo"))
        st.subheader(t("Probabilidades do modelo"))
        st.progress(float(bom), text=t("Bom: {probabilidade:.1%}", probabilidade=bom))
        st.progress(float(ruim), text=t("Ruim: {probabilidade:.1%}", probabilidade=ruim))
        st.subheader(t("Raio-X das palavras"))
        st.markdown(html_raio_x(resultado), unsafe_allow_html=True)
        st.caption(t("Verde favorece BOM; vermelho favorece RUIM; sublinhado indica palavra fora do vocabulário."))
        st.caption(t("A influência é a diferença na probabilidade ao retirar cada palavra, mantendo as demais."))
        st.subheader(t("Diagnóstico técnico"))
        st.text_area(t("Detalhes da análise"), value=diagnostico_tecnico(resultado),
                     height=230, disabled=True)
        st.pyplot(grafico_leitura(resultado))
