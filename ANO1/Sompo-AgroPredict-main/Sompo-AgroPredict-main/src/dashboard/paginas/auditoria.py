"""
Auditoria de risco (US-03) — analista e admin.

Aderencia aos alertas (CA-03.1), score de comportamento preventivo do
produtor (CA-03.2), analise forense de sinistro (CA-03.3), auditoria
completa de uma predicao (CA-03.4), qualidade da coleta e trilha de acessos.
"""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import streamlit as st

from agropredict.entrada import FEATURES, Leitura, LeituraInvalida
from agropredict.integridade import hash_leitura
from agropredict.relatorios import FAIXAS_COMPORTAMENTO, MINIMO_PREDICOES_COMPORTAMENTO, PESOS_COMPORTAMENTO
from i18n import (
    formatar_data, formatar_numero, formato_data_input, idioma_atual, t, tr_acao, tr_classe, tr_faixa,
    tr_motivo_override, tr_origem, tr_recomendacao, tr_status, tr_variavel,
)
from ui_comum import (
    COR_SERIE_UNICA, EMOJI_RISCO, barra_filtros, botao_csv, contexto, exigir, explicacao_em_texto, tabela,
)

EMOJI_FAIXA = {"Excelente": "🟢", "Bom": "🔵", "Atenção": "🟡", "Crítico": "🔴", "Dados insuficientes": "⚪"}


def _aba_aderencia(ctx) -> None:
    filtros = barra_filtros("aud_ader", dias_padrao=30, com_status=False)
    df = ctx.relatorios.aderencia_operadores(filtros)
    if df.empty:
        st.info(t("Nenhum alerta no período."))
        return
    st.caption(t("Aderência = alertas respeitados ÷ alertas respondidos (pendentes não entram no cálculo)."))
    col_tab, col_graf = st.columns([3, 2])
    with col_tab:
        tabela(df, column_config={
            "aderencia_pct": st.column_config.ProgressColumn(
                t("Aderência"), min_value=0, max_value=100, format="%.1f%%"),
        })
    with col_graf:
        rotulo = t("Aderência (%)")
        st.bar_chart(df.set_index("operador")[["aderencia_pct"]].rename(columns={"aderencia_pct": rotulo}),
                     horizontal=True, color=COR_SERIE_UNICA, sort=f"-{rotulo}")
    botao_csv(df, "aderencia_operadores")


def _aba_comportamento(ctx) -> None:
    filtros = barra_filtros("aud_comp", dias_padrao=30, com_status=False)
    df = ctx.relatorios.comportamento_produtor(filtros)
    if df.empty:
        st.info(t("Nenhuma predição no período."))
        return
    faixas = " · ".join(
        f"{EMOJI_FAIXA[nome]} {tr_faixa(nome)} (≥{limite})" for limite, nome in FAIXAS_COMPORTAMENTO
    )
    st.caption(t(
        "Score de 0 a 100 por produtor segurado (fazenda): {aderencia}% aderência "
        "aos alertas + {baixo}% operações em risco BAIXO + "
        "{tendencia}% tendência do score no período (50 = estável). "
        "Exige {minimo}+ predições. Faixas: {faixas}.",
        aderencia=int(PESOS_COMPORTAMENTO["aderencia"] * 100),
        baixo=int(PESOS_COMPORTAMENTO["baixo"] * 100),
        tendencia=int(PESOS_COMPORTAMENTO["tendencia"] * 100),
        minimo=MINIMO_PREDICOES_COMPORTAMENTO, faixas=faixas,
    ))
    exibicao = df.assign(
        faixa=df["faixa"].map(lambda f: f"{EMOJI_FAIXA.get(f, '')} {tr_faixa(f)}")
    )
    tabela(exibicao, column_config={
        "score_comportamento": st.column_config.ProgressColumn(
            t("Score de comportamento"), min_value=0, max_value=100, format="%.1f"),
        "aderencia_pct": st.column_config.NumberColumn(t("Aderência"), format="%.1f%%"),
        "pct_baixo": st.column_config.NumberColumn(t("% BAIXO"), format="%.1f%%"),
        "tendencia_pts": st.column_config.NumberColumn(t("Tendência"), format="%.1f"),
    })
    st.caption(t(
        "Uso sugerido: bonificação na renovação da apólice para faixas Excelente/Bom e plano de ação "
        "preventiva para Atenção/Crítico."
    ))
    botao_csv(df, "comportamento_produtor")


def _aba_forense(ctx) -> None:
    equipamentos = ctx.repo.listar_equipamentos()
    rotulos = dict(zip(equipamentos["id_equipamento"], equipamentos["codigo"] + " · " + equipamentos["regiao"]))
    c1, c2, c3, c4 = st.columns(4)
    id_equip = c1.selectbox(t("Equipamento"), list(rotulos), format_func=rotulos.get, key="for_equip")
    dia = c2.date_input(t("Data do sinistro"), key="for_dia", format=formato_data_input())
    hora = c3.time_input(t("Hora do sinistro"), value=time(17, 0), key="for_hora")
    janela = c4.number_input(t("Janela anterior (h)"), min_value=0.5, max_value=72.0, value=2.0, step=0.5)

    df = ctx.relatorios.forense(int(id_equip), datetime.combine(dia, hora), janela)
    if df.empty:
        st.info(t("Nenhuma predição desse equipamento na janela informada."))
        return
    alertas = df["nivel_alerta"].notna().sum()
    ignorados = (df["acao_tomada"] == "IGNOROU").sum()
    m1, m2, m3 = st.columns(3)
    m1.metric(t("Predições na janela"), len(df))
    m2.metric(t("Alertas emitidos"), int(alertas))
    m3.metric(t("❌ Alertas ignorados"), int(ignorados))
    if alertas:
        st.warning(t("O sistema havia alertado o operador antes do horário informado."))
    tabela(df)
    botao_csv(df, f"forense_equip{int(id_equip)}")


def _aba_predicao(ctx) -> None:
    ultima = ctx.repo.consultar("SELECT MAX(id_predicao) AS id FROM predicoes")["id"][0]
    if pd.isna(ultima):
        st.info(t("Nenhuma predição registrada ainda."))
        return
    id_predicao = st.number_input(
        t("ID da predição (padrão: a mais recente)"), min_value=1, step=1,
        value=int(ultima), key="aud_id",
    )
    registro = ctx.relatorios.auditoria_predicao(int(id_predicao))
    if registro is None:
        st.info(t("Predição não encontrada."))
        return

    classe = registro["classe_risco"]
    st.markdown(t(
        "### {emoji} Predição #{id} · {classe} · score {score}",
        emoji=EMOJI_RISCO[classe], id=registro["id_predicao"], classe=tr_classe(classe),
        score=f"{registro['score_risco']:.2f}",
    ))
    st.caption(t(
        "{data} · {equipamento} ({regiao}) · operador {usuario} · origem {origem} · leitura #{leitura}",
        data=formatar_data(registro["data_hora"], com_hora=True), equipamento=registro["equipamento"],
        regiao=registro["regiao"], usuario=registro["usuario"], origem=tr_origem(registro["origem"]),
        leitura=registro["id_leitura"],
    ))

    col_ent, col_dec = st.columns(2)
    with col_ent:
        st.markdown(t("**Entradas e fonte de cada dado**"))
        fontes = {
            "umidade_solo": registro["fonte_umidade"], "chuva_24h": registro["fonte_clima"],
            "temperatura": registro["fonte_clima"], "velocidade": registro["fonte_velocidade"],
            "horas_operacao": registro["fonte_horas"], "idade_maquina": registro["fonte_idade"],
            "declividade": "simulado" if registro["origem"] == "simulador" else "manual",
            "status_operacao": "simulado" if registro["origem"] == "simulador" else "operador",
        }
        from i18n import tr_fonte

        tabela(pd.DataFrame([
            {"variavel": tr_variavel(v), "valor": str(registro[v]), "fonte": tr_fonte(f)}
            for v, f in fontes.items()
        ]), column_config={
            "variavel": st.column_config.Column(t("Variável")),
            "valor": st.column_config.Column(t("Valor")),
            "fonte": st.column_config.Column(t("Fonte")),
        }, height=35 * (len(fontes) + 1) + 3)
    with col_dec:
        st.markdown(t("**Decisão automatizada**"))
        replicado = t("sim") if registro["gravado_oracle"] else t("não")
        tabela(pd.DataFrame([
            {"item": t("Classe do modelo"), "valor": tr_classe(registro["classe_modelo"])},
            {"item": t("Classe final"), "valor": tr_classe(classe)},
            {"item": "P(BAIXO)", "valor": f"{registro['prob_baixo']:.4f}"},
            {"item": t("P(MÉDIO)"), "valor": f"{registro['prob_medio']:.4f}"},
            {"item": "P(ALTO)", "valor": f"{registro['prob_alto']:.4f}"},
            {"item": t("Score (risco esperado)"), "valor": f"{registro['score_risco']:.2f}"},
            {"item": t("Override de regra crítica"), "valor": tr_motivo_override(registro["motivo_override"]) or t("não")},
            {"item": t("Variáveis em alerta"), "valor": tr_variavel(registro["variaveis_alerta"]) if registro["variaveis_alerta"] else "—"},
            {"item": t("Recomendação"), "valor": tr_recomendacao(registro["recomendacao"])},
            {"item": t("Versão do modelo"), "valor": f"{registro['versao_modelo']} ({registro['hash_modelo']})"},
            {"item": t("Replicado no Oracle"), "valor": replicado},
            {"item": t("Integridade da leitura"), "valor": _integridade(registro)},
        ]), column_config={
            "item": st.column_config.Column(t("Item")),
            "valor": st.column_config.Column(t("Valor")),
        }, height=35 * 13 + 3)
    st.markdown(t("**Por que esse risco? (explicação local do modelo)**"))
    for linha in explicacao_em_texto(registro["explicacao"], registro["motivo_override"]):
        st.markdown(f"- {linha}")
    alerta = registro["alerta"]
    if alerta:
        st.markdown(t(
            "**Alerta:** nível {nivel} · categoria {categoria} · ação **{acao}** por {usuario} em {data}",
            nivel=tr_classe(alerta["nivel"]), categoria=t(alerta["categoria"]),
            acao=tr_acao(alerta["acao_tomada"]), usuario=alerta["usuario_acao"] or "—",
            data=formatar_data(alerta["data_acao"], com_hora=True) if alerta["data_acao"] else "—",
        ))
    st.caption(t(
        "Score = 0·P(BAIXO) + 50·P(MÉDIO) + 100·P(ALTO); override de regra crítica força ALTO e score 100."
    ))


def _integridade(registro: dict) -> str:
    if not registro.get("hash_entrada"):
        return t("sem hash (leitura anterior à Sprint 4)")
    try:
        leitura = Leitura.de_dict({c: registro[c] for c in FEATURES})
    except LeituraInvalida:
        return t("❌ leitura inválida no banco")
    atual = hash_leitura(leitura, registro["id_equipamento"], registro["data_hora"], registro["usuario"])
    return t("✅ hash SHA-256 confere") if atual == registro["hash_entrada"] else t("❌ hash não confere")


def _aba_qualidade(ctx) -> None:
    filtros = barra_filtros("aud_qual", dias_padrao=30, com_status=False)
    q = ctx.relatorios.qualidade_dados(filtros)
    status = q["status"].set_index("status")["leituras"].to_dict()
    integ = q["integridade"]
    rej = q["rejeicoes_por_tipo"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("Leituras recebidas"), int(integ["total"]))
    c2.metric(t("✅ Processadas"), int(status.get("PROCESSADA", 0)))
    c3.metric(t("⏳ Pendentes / ❌ erro"),
              f"{int(status.get('PENDENTE', 0))} / {int(status.get('ERRO', 0))}")
    c4.metric(t("Rejeitadas (inválidas)"), int(rej.get("INVALIDA", 0)))
    c5.metric(t("Rejeitadas (duplicadas)"), int(rej.get("DUPLICADA", 0)))
    st.caption(t(
        "Integridade: {com_hash} de {total} leituras com hash SHA-256 · "
        "{sem_predicao} leitura(s) processada(s) sem predição (esperado: 0).",
        com_hash=int(integ["com_hash"]), total=int(integ["total"]),
        sem_predicao=int(integ["processadas_sem_predicao"]),
    ))
    col_fontes, col_rej = st.columns([2, 3])
    with col_fontes:
        st.markdown(t("**Dados informados manualmente, por fonte**"))
        fontes = q["fontes"].copy()
        fontes["fonte"] = fontes["fonte"].map(lambda f: t(f))
        tabela(fontes, column_config={
            "pct_manual": st.column_config.ProgressColumn(
                t("% manual"), min_value=0, max_value=100, format="%.1f%%"),
        })
    with col_rej:
        st.markdown(t("**Entradas recusadas (rastreáveis)**"))
        rejeicoes = ctx.relatorios.rejeicoes(filtros)
        if rejeicoes.empty:
            st.caption(t("Nenhuma entrada recusada no período."))
        else:
            tabela(rejeicoes, height=260)
            botao_csv(rejeicoes, "rejeicoes")


def render() -> None:
    exigir("auditoria")
    ctx = contexto()
    st.title(t("🔎 Auditoria de risco"))
    aba_ader, aba_comp, aba_for, aba_pred, aba_qual, aba_log = st.tabs([
        t("🤝 Aderência aos alertas"), t("🏅 Comportamento do produtor"), t("🕵️ Análise forense"),
        t("🧾 Auditoria de predição"), t("🧪 Qualidade da coleta"), t("🔐 Log de acessos"),
    ])
    with aba_ader:
        _aba_aderencia(ctx)
    with aba_comp:
        _aba_comportamento(ctx)
    with aba_for:
        _aba_forense(ctx)
    with aba_pred:
        _aba_predicao(ctx)
    with aba_qual:
        _aba_qualidade(ctx)
    with aba_log:
        log = ctx.relatorios.log_acessos()
        tabela(log, height=420)
        botao_csv(log, "log_acessos")
