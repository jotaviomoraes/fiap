"""
Operacao em tempo real (US-01) — operador, gestor e admin.

A tela so coleta a entrada e exibe a saida. O calculo e a gravacao sao
feitos pelo ServicoAvaliacao: a leitura vai primeiro para o banco e o
servico a le de la para gerar a predicao.
"""

from __future__ import annotations

import time
from datetime import date

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from agropredict.clima import buscar_clima_atual
from agropredict.config import config_oracle
from agropredict.entrada import Leitura, LeituraInvalida, STATUS_VALIDOS
from agropredict.oracle import configurado as oracle_configurado
from agropredict.regras import ALERTA, MAXIMO
from agropredict.relatorios import Filtros
from agropredict.servico import ErroProcessamento, LeituraDuplicada
from gps import capturar_posicao, obter_velocidade_kmh
from i18n import formatar_numero, t, tr_classe, tr_motivo_override, tr_recomendacao, tr_status
from ui_comum import (
    CORES_RISCO, EMOJI_ACAO, EMOJI_RISCO, contexto, emitir_sinal, exigir, explicacao_em_texto, formatar_hhmm,
    rotulo_classe, tabela,
)

INTERVALO_MIN_GRAVACAO = 10  # segundos — mesmo ritmo do ciclo de telemetria


def _avaliar_previa(ctx, dados: dict):
    """Reutiliza a ultima previa da sessao enquanto leitura e modelo forem iguais."""
    leitura = Leitura.de_dict(dados)
    chave = (ctx.servico.modelo, leitura)
    previa = st.session_state.get("_previa_operacao")
    if previa is None or previa[0] != chave:
        previa = (chave, ctx.servico.avaliar(leitura))
        st.session_state["_previa_operacao"] = previa
    return previa[1]


@st.cache_data(ttl=600, show_spinner=False)  # cache de 10 min por coordenada
def _clima(lat: float, lon: float) -> dict:
    return buscar_clima_atual(lat, lon)


@st.cache_data(ttl=60)
def _historico_oracle():
    config = config_oracle()
    if not oracle_configurado(config):
        return None
    try:
        import oracledb
        with oracledb.connect(**config) as conn:
            return pd.read_sql("""
                SELECT id_predicao, data_hora, id_equipamento, classe_risco, score_risco,
                       prob_baixo, prob_medio, prob_alto, versao_modelo, recomendacao
                FROM predicoes ORDER BY data_hora DESC FETCH FIRST 100 ROWS ONLY
            """, conn)
    except Exception:
        return None


def label_alerta(valor, chave):
    """Retorna delta string para st.metric com icone coerente."""
    if chave in MAXIMO and valor >= MAXIMO[chave]:
        return t("🔴 MAX")
    if valor > ALERTA[chave]:
        return t("⚠️ Alerta")
    return t("✅ OK")


def _sidebar_entradas(ctx):
    """Coleta as 8 features + equipamento + origem de cada dado."""
    equipamentos = ctx.repo.listar_equipamentos()
    rotulos = {
        int(r.id_equipamento): f"{r.codigo} · {r.tipo} {r.modelo} ({r.regiao})"
        for r in equipamentos.itertuples()
    }
    st.sidebar.markdown(t("### 🚜 Equipamento"))
    id_equipamento = st.sidebar.selectbox(
        t("Equipamento em operação"), list(rotulos), format_func=rotulos.get, key="op_equipamento"
    )
    equip = ctx.repo.obter_equipamento(id_equipamento)

    modo_real = st.sidebar.toggle(
        t("📡 Usar GPS + clima em tempo real"), value=True,
        help=t("Desative para digitar tudo manualmente (modo demo/offline)."),
    )
    # O contador do autorefresh varia a key do GPS e forca uma NOVA leitura a cada ciclo.
    ciclo = st_autorefresh(interval=10_000, key="_refresh_telemetria") if modo_real else 0

    with st.sidebar.expander(t("✍️ Substituir algum campo manualmente")):
        st.caption(t("Marque se o sensor correspondente não conectou hoje."))
        manual_velocidade = st.checkbox(t("Velocidade"), key="manual_velocidade")
        manual_clima = st.checkbox(t("Temperatura / Chuva"), key="manual_clima")
        manual_umidade = st.checkbox(t("Umidade do solo"), key="manual_umidade")
        manual_horas = st.checkbox(t("Horas de operação"), key="manual_horas")
        manual_idade = st.checkbox(t("Idade da máquina"), key="manual_idade")

    posicao = capturar_posicao(ciclo) if modo_real else None
    velocidade_gps, origem_velocidade = obter_velocidade_kmh(posicao) if modo_real else (None, "indisponivel")
    clima = _clima(posicao["lat"], posicao["lon"]) if modo_real and posicao and posicao.get("lat") is not None else None

    st.sidebar.markdown(t("### 📍 Status da telemetria"))
    if modo_real:
        if posicao is None:
            st.sidebar.warning(t("Aguardando permissão de localização do navegador…"))
        else:
            st.sidebar.caption(
                t("GPS: {lat}, {lon} (±{acc}m) · leitura #{ciclo}",
                  lat=f"{posicao['lat']:.5f}", lon=f"{posicao['lon']:.5f}",
                  acc=posicao.get("accuracy_m", "?"), ciclo=ciclo)
            )
        if clima and clima["ok"]:
            st.sidebar.caption(t("Clima: Open-Meteo · atualizado agora"))
        elif clima and not clima["ok"]:
            st.sidebar.error(t("Falha na API de clima: {erro}", erro=clima.get("erro", "")))
    else:
        st.sidebar.caption(t("Modo manual — sem captura em tempo real."))

    st.sidebar.markdown(t("### Variáveis ambientais"))
    umidade_auto = clima["umidade_solo"] if clima and clima.get("umidade_solo") is not None else None
    if manual_umidade or umidade_auto is None:
        umidade_solo = st.sidebar.slider(t("Umidade do solo (%)"), 0, 100, int(umidade_auto or 20))
        fonte_umidade = "manual"
    else:
        umidade_solo, fonte_umidade = umidade_auto, "open-meteo"
        st.sidebar.metric(t("Umidade do solo (auto)"), f"{umidade_solo:.0f}%")

    declividade = st.sidebar.slider(
        t("Declividade (%)"), 0, 25, 8,
        help=t("Ainda depende de mapa GIS/satélite por talhão — não coberto pelo GPS do celular."),
    )

    if manual_clima or not (clima and clima["ok"]):
        chuva_24h = st.sidebar.slider(t("Chuva 24h (mm)"), 0, 40, 4)
        temperatura = st.sidebar.slider(t("Temperatura (°C)"), 15, 45, 26)
        fonte_clima = "manual"
    else:
        chuva_24h, temperatura, fonte_clima = clima["chuva_24h"], clima["temperatura"], "open-meteo"
        st.sidebar.metric(t("Chuva 24h (auto)"), f"{chuva_24h:.1f} mm")
        st.sidebar.metric(t("Temperatura (auto)"), f"{temperatura:.1f}°C")

    st.sidebar.markdown(t("### Variáveis operacionais"))
    if manual_velocidade or velocidade_gps is None:
        velocidade, fonte_velocidade = st.sidebar.slider(t("Velocidade (km/h)"), 0, 20, 7), "manual"
        if modo_real and not manual_velocidade:
            st.sidebar.caption(t("⏳ Aguardando 2ª leitura de GPS para calcular velocidade…"))
    else:
        velocidade, fonte_velocidade = velocidade_gps, origem_velocidade
        st.sidebar.metric(t("Velocidade (auto)"), f"{velocidade:.1f} km/h", t(origem_velocidade))

    idade_cadastro = max(0, date.today().year - int(equip["ano_fabricacao"]))
    if manual_idade:
        idade_maquina = st.sidebar.slider(
            t("Idade da máquina (anos)"), 0, 20, min(idade_cadastro, 20)
        )
        fonte_idade = "manual"
    else:
        idade_maquina, fonte_idade = idade_cadastro, "cadastro"
        st.sidebar.metric(
            t("Idade da máquina (cadastro)"), t("{idade} anos", idade=idade_maquina),
            t("fabricação {ano}", ano=equip["ano_fabricacao"]),
        )

    # Horas de operacao: contador automatico que soma enquanto o GPS esta
    # conectado e PAUSA (sem "pular" tempo) quando o sinal cai.
    st.session_state.setdefault("_horas_acumuladas", 0.0)
    contando = modo_real and not manual_horas and posicao is not None
    if contando:
        agora = time.time()
        ultimo = st.session_state.get("_ultimo_tick_horas")
        if ultimo is not None:
            st.session_state["_horas_acumuladas"] += (agora - ultimo) / 3600
        st.session_state["_ultimo_tick_horas"] = agora
    else:
        st.session_state.pop("_ultimo_tick_horas", None)

    if manual_horas:
        horas_operacao = st.sidebar.slider(t("Horas de operação (acumuladas)"), 0, 14, 5)
        fonte_horas = "manual"
        st.sidebar.caption(t("≈ {hora}", hora=formatar_hhmm(horas_operacao)))
    else:
        horas_operacao = round(min(st.session_state["_horas_acumuladas"], 14.0), 2)
        fonte_horas = "gps_auto" if contando else "pausado"
        st.sidebar.metric(t("Horas de operação (auto)"), formatar_hhmm(horas_operacao), t(fonte_horas))
        if st.sidebar.button(t("🔄 Reiniciar contador de horas")):
            st.session_state["_horas_acumuladas"] = 0.0
            st.session_state.pop("_ultimo_tick_horas", None)
            st.rerun()

    status_operacao = st.sidebar.selectbox(t("Tipo de operação"), list(STATUS_VALIDOS), format_func=tr_status)

    dados = {
        "umidade_solo": umidade_solo, "declividade": declividade, "chuva_24h": chuva_24h,
        "temperatura": temperatura, "velocidade": velocidade, "idade_maquina": idade_maquina,
        "horas_operacao": horas_operacao, "status_operacao": status_operacao,
    }
    fontes = {
        "umidade": fonte_umidade, "clima": fonte_clima, "velocidade": fonte_velocidade,
        "horas": fonte_horas, "idade": fonte_idade,
    }
    return equip, modo_real, dados, fontes, posicao


def _painel_alertas_pendentes(ctx, sessao, id_equipamento: int) -> None:
    pendentes = ctx.relatorios.listar_alertas(
        Filtros(equipamentos=[id_equipamento]), acoes=["PENDENTE"], limite=5
    )
    st.subheader(t("{emoji} Alertas pendentes deste equipamento", emoji=EMOJI_ACAO["PENDENTE"]))
    if pendentes.empty:
        st.caption(t("Nenhum alerta aguardando resposta."))
        return
    pode_responder = sessao.pode("responder_alerta")
    for alerta in pendentes.itertuples():
        col_txt, col_ok, col_nok = st.columns([4, 1, 1])
        col_txt.markdown(
            f"{EMOJI_RISCO[alerta.nivel]} **#{alerta.id_alerta}** · {alerta.data_emissao} · "
            f"{tr_recomendacao(alerta.mensagem)}"
        )
        if pode_responder:
            if col_ok.button(t("Respeitei"), key=f"ok_{alerta.id_alerta}"):
                ctx.servico.responder_alerta(alerta.id_alerta, "RESPEITOU", sessao.usuario)
                st.rerun()
            if col_nok.button(t("Ignorei"), key=f"nok_{alerta.id_alerta}"):
                ctx.servico.responder_alerta(alerta.id_alerta, "IGNOROU", sessao.usuario)
                st.rerun()


def render() -> None:
    sessao = exigir("operacao")
    ctx = contexto()
    equip, modo_real, dados, fontes, posicao = _sidebar_entradas(ctx)
    som_ativo = st.sidebar.toggle(
        t("🔊 Alerta sonoro e vibração"), value=True, key="op_som",
        help=t("Sinal curto ao entrar em MÉDIO; sinal repetido e vibração em ALTO."),
    )

    # ------------------------------------------------------------------
    # Previa (sem gravar) — mesma funcao de avaliacao usada na gravacao
    # ------------------------------------------------------------------
    try:
        _, avaliacao = _avaliar_previa(ctx, dados)
    except LeituraInvalida as exc:
        st.error(t("❌ Leitura rejeitada pela validação de entrada — nada foi gravado."))
        for problema in exc.problemas:
            from i18n import tr_motivo_rejeicao
            st.markdown(f"- {tr_motivo_rejeicao(problema)}")
        st.info(t("Use **Substituir algum campo manualmente** na barra lateral para corrigir o dado."))
        st.stop()

    # ------------------------------------------------------------------
    # Persistencia: entrada -> banco -> modelo -> saida, pelo servico
    # ------------------------------------------------------------------
    # Gravacao automatica so com GPS conectado: sem sinal, os sliders padrao
    # nao devem virar leituras "reais" no banco a cada ciclo.
    agora_ts = time.time()
    telemetria_ativa = modo_real and posicao is not None
    gravar_auto = (
        telemetria_ativa and agora_ts - st.session_state.get("_ultimo_save", 0) >= INTERVALO_MIN_GRAVACAO
    )
    gravar_manual = (
        st.sidebar.button(t("💾 Registrar leitura"), type="primary", width="stretch") if not telemetria_ativa else False
    )

    resultado = None
    if gravar_auto or gravar_manual:
        try:
            resultado = ctx.servico.processar(
                dados, equip["id_equipamento"], sessao.usuario,
                origem="dashboard", fontes=fontes, posicao=posicao,
            )
            avaliacao = resultado.avaliacao
            st.session_state["_ultimo_save"] = agora_ts
            st.session_state["_ultimo_resultado"] = (resultado.id_leitura, resultado.id_predicao, resultado.id_alerta)
        except LeituraDuplicada as exc:
            st.session_state["_ultimo_save"] = agora_ts
            st.info(t("ℹ️ Leitura idêntica à #{id} já registrada — não foi gravada de novo.", id=exc.id_existente))
        except (ErroProcessamento, ValueError) as exc:
            st.error(t("❌ Falha ao registrar a leitura: {erro}", erro=exc))

    # ------------------------------------------------------------------
    # Saida
    # ------------------------------------------------------------------
    st.title(t("🌾 AgroPredict — Operação em tempo real"))
    st.caption(
        f"{equip['codigo']} · {equip['tipo']} {equip['fabricante']} {equip['modelo']} · "
        f"{equip['fazenda']} · {equip['regiao']}"
    )

    ultimo = st.session_state.get("_ultimo_resultado")
    if resultado:
        extra = t(" → alerta #{id}", id=resultado.id_alerta) if resultado.id_alerta else ""
        st.success(t(
            "💾 Leitura #{leitura} → predição #{predicao}{extra} gravadas no banco.",
            leitura=resultado.id_leitura, predicao=resultado.id_predicao, extra=extra,
        ))
    elif ultimo:
        st.caption(t(
            "Última gravação: leitura #{leitura} → predição #{predicao}. Exibindo prévia da leitura atual.",
            leitura=ultimo[0], predicao=ultimo[1],
        ))
    elif not telemetria_ativa:
        st.info(t("Prévia — ainda não gravada. Use **💾 Registrar leitura** na barra lateral."))

    classe = avaliacao.classe_risco
    # US-01: sinal curto na transicao para MEDIO; sinal repetido + vibracao a cada ciclo em ALTO
    anterior = st.session_state.get("_classe_sinalizada")
    if som_ativo and (classe == "ALTO" or (classe == "MEDIO" and anterior != "MEDIO")):
        emitir_sinal(classe)
    st.session_state["_classe_sinalizada"] = classe

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(
            f"""
            <div style='background-color:{CORES_RISCO[classe]};padding:30px;
                        border-radius:12px;color:white;text-align:center;'>
                <h1 style='margin:0;font-size:60px;color:white;'>{EMOJI_RISCO[classe]} {tr_classe(classe)}</h1>
                <h2 style='margin:5px 0;color:white;'>{t("Score")}: {avaliacao.score_risco:.1f} / 100</h2>
                <p style='margin:10px 0 0 0;font-size:18px;'><strong>{tr_recomendacao(avaliacao.recomendacao)}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if avaliacao.override_aplicado:
            st.warning(t("⚡ **Override ativado:** {motivo}", motivo=tr_motivo_override(avaliacao.motivo_override)))
        elif avaliacao.variaveis_alerta:
            from i18n import tr_lista_variaveis
            st.info(t(
                "⚠️ {n} variável(is) em alerta: {variaveis}",
                n=len(avaliacao.variaveis_alerta), variaveis=tr_lista_variaveis(",".join(avaliacao.variaveis_alerta)),
            ))
        if avaliacao.gera_alerta:
            st.error(t(
                "🚨 Esta leitura gera alerta **{classe}** (categoria {categoria}).",
                classe=tr_classe(classe), categoria=t(avaliacao.categoria_alerta or ""),
            ))
        with st.expander(t("❓ Por que esse risco?"), expanded=classe != "BAIXO"):
            for linha in explicacao_em_texto(avaliacao.explicacao, avaliacao.motivo_override):
                st.markdown(f"- {linha}")
            st.caption(t(
                "Impacto = quanto o score cairia se a variável estivesse no valor típico de uma "
                "operação segura. Calculado para esta leitura, pelo próprio modelo."
            ))

    with col2:
        st.markdown(t("### Probabilidades"))
        for c in ("BAIXO", "MEDIO", "ALTO"):
            p = avaliacao.prob(c)
            st.markdown(f"**{rotulo_classe(c)}**")
            st.progress(float(p))
            st.caption(f"{p * 100:.1f}%")

    with col3:
        st.markdown(t("### Contexto"))
        st.metric(t("Operação"), tr_status(dados["status_operacao"]))
        st.metric(t("Classe do modelo"), tr_classe(avaliacao.classe_modelo))
        st.caption(t("Modelo {versao} · {hash}", versao=avaliacao.versao_modelo, hash=avaliacao.hash_modelo))

    st.markdown("---")
    st.subheader(t("📊 Detalhes da operação avaliada"))
    d = dados
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric(t("Umidade do solo"), f"{formatar_numero(d['umidade_solo'])}%",
                 label_alerta(d["umidade_solo"], "umidade_solo"))
    col_b.metric(t("Declividade"), f"{formatar_numero(d['declividade'])}%",
                 label_alerta(d["declividade"], "declividade"))
    col_c.metric(t("Chuva 24h"), f"{formatar_numero(d['chuva_24h'], 1)} mm",
                 label_alerta(d["chuva_24h"], "chuva_24h"))
    col_d.metric(t("Temperatura"), f"{formatar_numero(d['temperatura'], 1)}°C",
                 label_alerta(d["temperatura"], "temperatura"))
    col_e, col_f, col_g, col_h = st.columns(4)
    col_e.metric(t("Velocidade"), f"{formatar_numero(d['velocidade'], 1)} km/h",
                 label_alerta(d["velocidade"], "velocidade"))
    col_f.metric(t("Idade máquina"), t("{idade} anos", idade=formatar_numero(d["idade_maquina"])),
                 label_alerta(d["idade_maquina"], "idade_maquina"))
    col_g.metric(t("Horas operação"), formatar_hhmm(d["horas_operacao"]),
                 label_alerta(d["horas_operacao"], "horas_operacao"))
    col_h.metric(t("Tipo"), tr_status(d["status_operacao"]))

    st.markdown("---")
    _painel_alertas_pendentes(ctx, sessao, equip["id_equipamento"])

    st.markdown("---")
    st.subheader(t("🔍 Quais variáveis mais influenciam o modelo?"))
    st.caption(t(
        "Importância global por permutação do modelo {versao}: quanto o F1 cai quando a "
        "variável é embaralhada. Para a explicação de uma leitura específica, veja "
        "**Por que esse risco?** acima.",
        versao=ctx.servico.modelo.versao,
    ))
    importancias = ctx.servico.modelo.importancias().copy()
    importancias["feature"] = importancias["feature"].map(
        lambda f: t(f) if f in {
            "Umidade do solo", "Declividade", "Chuva 24h", "Temperatura", "Velocidade",
            "Idade da máquina", "Horas de operação",
        } else f
    )
    st.bar_chart(importancias.set_index("feature"), horizontal=True,
                 color="#2a78d6", sort="-importancia")

    st.markdown("---")
    st.subheader(t("📅 Últimas predições deste equipamento"))
    backend = getattr(ctx, "backend", "sqlite")
    if backend == "oracle":
        historico = ctx.repo.consultar(
            """SELECT id_predicao, data_hora, usuario, classe_risco, score_risco,
                      prob_baixo, prob_medio, prob_alto, override_aplicado, recomendacao,
                      fonte_clima, fonte_velocidade, fonte_horas, versao_modelo, acao_tomada
               FROM vw_predicoes WHERE id_equipamento = ? ORDER BY data_hora DESC LIMIT 50""",
            [equip["id_equipamento"]],
        )
        st.success(t("✅ Banco principal: Oracle. {n} predições recentes.", n=len(historico)))
        if historico.empty:
            st.caption(t("Nenhuma predição registrada para este equipamento ainda."))
        else:
            tabela(historico, height=320)
    else:
        tab_local, tab_oracle = st.tabs([t("💾 SQLite (fallback local)"), t("🗄️ Oracle (réplica opcional)")])
        with tab_local:
            historico = ctx.repo.consultar(
                """SELECT id_predicao, data_hora, usuario, classe_risco, score_risco,
                          prob_baixo, prob_medio, prob_alto, override_aplicado, recomendacao,
                          fonte_clima, fonte_velocidade, fonte_horas, versao_modelo, acao_tomada
                   FROM vw_predicoes WHERE id_equipamento = ? ORDER BY data_hora DESC LIMIT 50""",
                [equip["id_equipamento"]],
            )
            if historico.empty:
                st.caption(t("Nenhuma predição registrada para este equipamento ainda."))
            else:
                tabela(historico, height=320)
        with tab_oracle:
            historico_oracle = _historico_oracle()
            if historico_oracle is not None and len(historico_oracle) > 0:
                st.success(t("✅ Conectado ao Oracle. {n} predições recentes.", n=len(historico_oracle)))
                tabela(historico_oracle)
            else:
                st.info(t("ℹ️ Oracle não configurado ou indisponível. O SQLite continua registrando tudo."))
