"""Raio X: evidências de avaliação, comparação e limitações dos classificadores."""

import altair as alt
import pandas as pd
import streamlit as st

from agropredict.diagnostico import carregar_diagnostico, vencedor_risco
from i18n import formatar_numero, t
from ui_comum import exigir

CORES_MODELOS = {
    "Regressão Logística (baseline)": "#2563eb", "Random Forest": "#d97706",
    "Gradient Boosting": "#16a34a",
}


def _grafico_linhas(linhas, categorias, eixo_x, eixo_y, series, cores,
                    altura=320, limites_y=(80, 100), passo_y=5):
    """Ordem categórica explícita, cores estáveis e escala comum nas porcentagens."""
    escala = alt.Scale(domain=list(limites_y), zero=False, nice=False)
    eixo = alt.Axis(values=list(range(limites_y[0], limites_y[1] + 1, passo_y)),
                    grid=True, labelOverlap=False) if passo_y else alt.Axis()
    cor = alt.Color("serie:N", title=t("Série"),
                    scale=alt.Scale(domain=series, range=cores),
                    legend=alt.Legend(orient="bottom", direction="vertical", columns=1, labelLimit=400))
    eixos = dict(
        x=alt.X("categoria:N", sort=categorias, title=eixo_x, axis=alt.Axis(labelAngle=0, labelLimit=200)),
        y=alt.Y("valor:Q", title=eixo_y, scale=escala, axis=eixo),
        color=cor,
        tooltip=[alt.Tooltip("serie:N", title=t("Série")),
                 alt.Tooltip("categoria:N", title=eixo_x),
                 alt.Tooltip("valor:Q", title=eixo_y, format=".2f")],
    )
    grafico = alt.Chart(pd.DataFrame(linhas)).mark_line(point=True, strokeWidth=2, clip=True).encode(
        **eixos, order=alt.Order("ordem:Q"))
    grafico = grafico.transform_filter(alt.FieldRangePredicate(field="valor", range=list(limites_y)))
    return grafico.properties(height=altura)


def _percentual(valor):
    return f"{formatar_numero(valor * 100, 2)}%"


def _comparacao(risco):
    candidatos = risco.get("candidatos", {})
    if not candidatos:
        return
    st.subheader(t("Comparação dos candidatos de risco"))
    metricas = [(t("Acurácia"), "acuracia_cv"), ("F1 macro", "f1_macro_cv"),
                (t("Recall ALTO (%)"), "recall_alto_cv")]
    linhas = [{"serie": t(nome), "categoria": rotulo, "valor": c[chave] * 100, "ordem": i}
              for nome, c in candidatos.items() for i, (rotulo, chave) in enumerate(metricas)]
    st.altair_chart(_grafico_linhas(
        linhas, [rotulo for rotulo, _ in metricas], t("Métrica"), t("Validação cruzada (%)"),
        [t(nome) for nome in candidatos], [CORES_MODELOS[nome] for nome in candidatos], altura=320,
        limites_y=(80, 100), passo_y=5),
        width="stretch")
    st.caption(t("Escala de 80% a 100%, com linhas a cada 5 pontos percentuais, incluindo as métricas da regressão logística."))
    st.caption(t("Mesma base, divisão estratificada e validação cruzada de 5 partes no treino. Quanto maior, melhor; estas linhas não são resultados de teste."))
    vencedor = vencedor_risco(candidatos)
    if vencedor:
        c = candidatos[vencedor]
        st.success(t("{modelo} venceu: F1 macro de {f1} na validação cruzada, com recall de ALTO de {recall}. O critério exige recall de ALTO ≥ 95% e, entre os elegíveis, o maior F1 macro.",
                     modelo=t(vencedor), f1=_percentual(c["f1_macro_cv"]),
                     recall=_percentual(c["recall_alto_cv"])))
    for nome, c in candidatos.items():
        if c["recall_alto_cv"] < .95:
            st.caption(t("{modelo} não atingiu o recall mínimo de ALTO: {recall}.",
                         modelo=t(nome), recall=_percentual(c["recall_alto_cv"])))
    st.caption(t("O modelo final passou por remoção de variável após a seleção. Por isso suas métricas diferem das do candidato Gradient Boosting."))



def render():
    exigir("raio_x")
    st.title(t("🔬 Raio X dos modelos"))
    st.caption(t("Diagnóstico das métricas salvas no treinamento. Esta página lê apenas JSON; não treina nem executa os modelos."))
    st.caption(t("As linhas conectam categorias para facilitar a comparação; não representam evolução temporal. Passe o mouse sobre os pontos para consultar os valores."))
    st.info(t("Todos os modelos avaliados fazem classificação. R², MAE e RMSE de regressão não se aplicam. O score de risco de 0 a 100 é derivado de probabilidades e regras, sem avaliação de regressão registrada."))
    dados = carregar_diagnostico()
    for arquivo in dados["indisponiveis"]:
        st.warning(t("Métricas indisponíveis: {arquivo}", arquivo=arquivo))
    if not dados["modelos"]:
        return
    risco = dados["risco"]
    _comparacao(risco)
    st.divider()
    st.subheader(t("Limites desta avaliação"))
    st.warning(t("O risco foi avaliado em dados sintéticos. O conjunto de teste também orientou a decisão de calibração; não é uma validação externa independente. O artefato final foi retreinado com todos os dados: as métricas exibidas são as registradas antes desse retreino."))
    st.caption(t("Não há medições registradas de latência, memória ou desempenho em produção para comparar os modelos."))
    with st.expander(t("Como interpretar as métricas")):
        st.write(t("Acurácia: fração total de acertos. Acurácia balanceada: média do recall das classes. F1 macro: média do equilíbrio entre precisão e recall de cada classe, com o mesmo peso para todas."))
        st.write(t("Precisão: entre as previsões de uma classe, quantas estavam corretas. Recall: entre os casos reais daquela classe, quantos foram encontrados. Recall de ALTO evita deixar passar situações de risco elevado."))
        st.write(t("Melhor significa melhor segundo o critério e a base avaliados. Diferenças pequenas exigem análise de incerteza e validação com dados reais antes de concluir superioridade em produção."))
