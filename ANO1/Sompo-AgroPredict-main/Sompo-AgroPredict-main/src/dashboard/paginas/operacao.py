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
from agropredict.entrada import LeituraInvalida, STATUS_VALIDOS
from agropredict.oracle import configurado as oracle_configurado
from agropredict.regras import ALERTA, MAXIMO
from agropredict.relatorios import Filtros
from agropredict.servico import ErroProcessamento, LeituraDuplicada
from gps import capturar_posicao, obter_velocidade_kmh
from ui_comum import (
    CORES_RISCO, EMOJI_ACAO, EMOJI_RISCO, contexto, emitir_sinal, exigir, explicacao_em_texto, formatar_hhmm,
    rotulo_classe, tabela,
)

INTERVALO_MIN_GRAVACAO = 10  # segundos — mesmo ritmo do ciclo de telemetria


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
        return "🔴 MAX"
    if valor > ALERTA[chave]:
        return "⚠️ Alerta"
    return "✅ OK"


def _sidebar_entradas(ctx):
    """Coleta as 8 features + equipamento + origem de cada dado."""
    equipamentos = ctx.repo.listar_equipamentos()
    rotulos = {
        int(r.id_equipamento): f"{r.codigo} · {r.tipo} {r.modelo} ({r.regiao})"
        for r in equipamentos.itertuples()
    }
    st.sidebar.markdown("### 🚜 Equipamento")
    id_equipamento = st.sidebar.selectbox(
        "Equipamento em operação", list(rotulos), format_func=rotulos.get, key="op_equipamento"
    )
    equip = ctx.repo.obter_equipamento(id_equipamento)

    modo_real = st.sidebar.toggle(
        "📡 Usar GPS + clima em tempo real", value=True,
        help="Desative para digitar tudo manualmente (modo demo/offline).",
    )
    # O contador do autorefresh varia a key do GPS e forca uma NOVA leitura a cada ciclo.
    ciclo = st_autorefresh(interval=10_000, key="_refresh_telemetria") if modo_real else 0

    with st.sidebar.expander("✍️ Substituir algum campo manualmente"):
        st.caption("Marque se o sensor correspondente não conectou hoje.")
        manual_velocidade = st.checkbox("Velocidade", key="manual_velocidade")
        manual_clima = st.checkbox("Temperatura / Chuva", key="manual_clima")
        manual_umidade = st.checkbox("Umidade do solo", key="manual_umidade")
        manual_horas = st.checkbox("Horas de operação", key="manual_horas")
        manual_idade = st.checkbox("Idade da máquina", key="manual_idade")

    posicao = capturar_posicao(ciclo) if modo_real else None
    velocidade_gps, origem_velocidade = obter_velocidade_kmh(posicao) if modo_real else (None, "indisponivel")
    clima = _clima(posicao["lat"], posicao["lon"]) if modo_real and posicao and posicao.get("lat") is not None else None

    st.sidebar.markdown("### 📍 Status da telemetria")
    if modo_real:
        if posicao is None:
            st.sidebar.warning("Aguardando permissão de localização do navegador…")
        else:
            st.sidebar.caption(
                f"GPS: {posicao['lat']:.5f}, {posicao['lon']:.5f} "
                f"(±{posicao.get('accuracy_m', '?')}m) · leitura #{ciclo}"
            )
        if clima and clima["ok"]:
            st.sidebar.caption("Clima: Open-Meteo · atualizado agora")
        elif clima and not clima["ok"]:
            st.sidebar.error(f"Falha na API de clima: {clima.get('erro', '')}")
    else:
        st.sidebar.caption("Modo manual — sem captura em tempo real.")

    st.sidebar.markdown("### Variáveis ambientais")
    umidade_auto = clima["umidade_solo"] if clima and clima.get("umidade_solo") is not None else None
    if manual_umidade or umidade_auto is None:
        umidade_solo, fonte_umidade = st.sidebar.slider("Umidade do solo (%)", 0, 100, int(umidade_auto or 20)), "manual"
    else:
        umidade_solo, fonte_umidade = umidade_auto, "open-meteo"
        st.sidebar.metric("Umidade do solo (auto)", f"{umidade_solo:.0f}%")

    declividade = st.sidebar.slider(
        "Declividade (%)", 0, 25, 8,
        help="Ainda depende de mapa GIS/satélite por talhão — não coberto pelo GPS do celular.",
    )

    if manual_clima or not (clima and clima["ok"]):
        chuva_24h = st.sidebar.slider("Chuva 24h (mm)", 0, 40, 4)
        temperatura = st.sidebar.slider("Temperatura (°C)", 15, 45, 26)
        fonte_clima = "manual"
    else:
        chuva_24h, temperatura, fonte_clima = clima["chuva_24h"], clima["temperatura"], "open-meteo"
        st.sidebar.metric("Chuva 24h (auto)", f"{chuva_24h:.1f} mm")
        st.sidebar.metric("Temperatura (auto)", f"{temperatura:.1f}°C")

    st.sidebar.markdown("### Variáveis operacionais")
    if manual_velocidade or velocidade_gps is None:
        velocidade, fonte_velocidade = st.sidebar.slider("Velocidade (km/h)", 0, 20, 7), "manual"
        if modo_real and not manual_velocidade:
            st.sidebar.caption("⏳ Aguardando 2ª leitura de GPS para calcular velocidade…")
    else:
        velocidade, fonte_velocidade = velocidade_gps, origem_velocidade
        st.sidebar.metric("Velocidade (auto)", f"{velocidade:.1f} km/h", origem_velocidade)

    idade_cadastro = max(0, date.today().year - int(equip["ano_fabricacao"]))
    if manual_idade:
        idade_maquina, fonte_idade = st.sidebar.slider("Idade da máquina (anos)", 0, 20, min(idade_cadastro, 20)), "manual"
    else:
        idade_maquina, fonte_idade = idade_cadastro, "cadastro"
        st.sidebar.metric("Idade da máquina (cadastro)", f"{idade_maquina} anos", f"fabricação {equip['ano_fabricacao']}")

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
        horas_operacao, fonte_horas = st.sidebar.slider("Horas de operação (acumuladas)", 0, 14, 5), "manual"
        st.sidebar.caption(f"≈ {formatar_hhmm(horas_operacao)}")
    else:
        horas_operacao = round(min(st.session_state["_horas_acumuladas"], 14.0), 2)
        fonte_horas = "gps_auto" if contando else "pausado"
        st.sidebar.metric("Horas de operação (auto)", formatar_hhmm(horas_operacao), fonte_horas)
        if st.sidebar.button("🔄 Reiniciar contador de horas"):
            st.session_state["_horas_acumuladas"] = 0.0
            st.session_state.pop("_ultimo_tick_horas", None)
            st.rerun()

    status_operacao = st.sidebar.selectbox("Tipo de operação", list(STATUS_VALIDOS))

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
    st.subheader(f"{EMOJI_ACAO['PENDENTE']} Alertas pendentes deste equipamento")
    if pendentes.empty:
        st.caption("Nenhum alerta aguardando resposta.")
        return
    pode_responder = sessao.pode("responder_alerta")
    for alerta in pendentes.itertuples():
        col_txt, col_ok, col_nok = st.columns([4, 1, 1])
        col_txt.markdown(
            f"{EMOJI_RISCO[alerta.nivel]} **#{alerta.id_alerta}** · {alerta.data_emissao} · {alerta.mensagem}"
        )
        if pode_responder:
            if col_ok.button("Respeitei", key=f"ok_{alerta.id_alerta}"):
                ctx.servico.responder_alerta(alerta.id_alerta, "RESPEITOU", sessao.usuario)
                st.rerun()
            if col_nok.button("Ignorei", key=f"nok_{alerta.id_alerta}"):
                ctx.servico.responder_alerta(alerta.id_alerta, "IGNOROU", sessao.usuario)
                st.rerun()


def render() -> None:
    sessao = exigir("operacao")
    ctx = contexto()
    equip, modo_real, dados, fontes, posicao = _sidebar_entradas(ctx)
    som_ativo = st.sidebar.toggle("🔊 Alerta sonoro e vibração", value=True, key="op_som",
                                  help="Sinal curto ao entrar em MÉDIO; sinal repetido e vibração em ALTO.")

    # ------------------------------------------------------------------
    # Previa (sem gravar) — mesma funcao de avaliacao usada na gravacao
    # ------------------------------------------------------------------
    try:
        _, avaliacao = ctx.servico.avaliar(dados)
    except LeituraInvalida as exc:
        st.error("❌ Leitura rejeitada pela validação de entrada — nada foi gravado.")
        for problema in exc.problemas:
            st.markdown(f"- {problema}")
        st.info("Use **Substituir algum campo manualmente** na barra lateral para corrigir o dado.")
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
        st.sidebar.button("💾 Registrar leitura", type="primary", width="stretch") if not telemetria_ativa else False
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
            st.info(f"ℹ️ Leitura idêntica à #{exc.id_existente} já registrada — não foi gravada de novo.")
        except (ErroProcessamento, ValueError) as exc:
            st.error(f"❌ Falha ao registrar a leitura: {exc}")

    # ------------------------------------------------------------------
    # Saida
    # ------------------------------------------------------------------
    st.title("🌾 Sompo AgroPredict — Operação em tempo real")
    st.caption(
        f"{equip['codigo']} · {equip['tipo']} {equip['fabricante']} {equip['modelo']} · "
        f"{equip['fazenda']} · {equip['regiao']}"
    )

    ultimo = st.session_state.get("_ultimo_resultado")
    if resultado:
        extra = f" → alerta #{resultado.id_alerta}" if resultado.id_alerta else ""
        st.success(f"💾 Leitura #{resultado.id_leitura} → predição #{resultado.id_predicao}{extra} gravadas no SQLite.")
    elif ultimo:
        st.caption(f"Última gravação: leitura #{ultimo[0]} → predição #{ultimo[1]}. Exibindo prévia da leitura atual.")
    elif not telemetria_ativa:
        st.info("Prévia — ainda não gravada. Use **💾 Registrar leitura** na barra lateral.")

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
                <h1 style='margin:0;font-size:60px;color:white;'>{EMOJI_RISCO[classe]} {classe}</h1>
                <h2 style='margin:5px 0;color:white;'>Score: {avaliacao.score_risco:.1f} / 100</h2>
                <p style='margin:10px 0 0 0;font-size:18px;'><strong>{avaliacao.recomendacao}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if avaliacao.override_aplicado:
            st.warning(f"⚡ **Override ativado:** {avaliacao.motivo_override}")
        elif avaliacao.variaveis_alerta:
            st.info(f"⚠️ {len(avaliacao.variaveis_alerta)} variável(is) em alerta: "
                    f"{', '.join(avaliacao.variaveis_alerta)}")
        if avaliacao.gera_alerta:
            st.error(f"🚨 Esta leitura gera alerta **{classe}** (categoria {avaliacao.categoria_alerta}).")
        with st.expander("❓ Por que esse risco?", expanded=classe != "BAIXO"):
            for linha in explicacao_em_texto(avaliacao.explicacao, avaliacao.motivo_override):
                st.markdown(f"- {linha}")
            st.caption("Impacto = quanto o score cairia se a variável estivesse no valor típico de uma "
                       "operação segura. Calculado para esta leitura, pelo próprio modelo.")

    with col2:
        st.markdown("### Probabilidades")
        for c in ("BAIXO", "MEDIO", "ALTO"):
            p = avaliacao.prob(c)
            st.markdown(f"**{rotulo_classe(c)}**")
            st.progress(float(p))
            st.caption(f"{p * 100:.1f}%")

    with col3:
        st.markdown("### Contexto")
        st.metric("Operação", dados["status_operacao"])
        st.metric("Classe do modelo", avaliacao.classe_modelo)
        st.caption(f"Modelo {avaliacao.versao_modelo} · {avaliacao.hash_modelo}")

    st.markdown("---")
    st.subheader("📊 Detalhes da operação avaliada")
    d = dados
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Umidade do solo", f"{d['umidade_solo']}%", label_alerta(d["umidade_solo"], "umidade_solo"))
    col_b.metric("Declividade", f"{d['declividade']}%", label_alerta(d["declividade"], "declividade"))
    col_c.metric("Chuva 24h", f"{d['chuva_24h']} mm", label_alerta(d["chuva_24h"], "chuva_24h"))
    col_d.metric("Temperatura", f"{d['temperatura']}°C", label_alerta(d["temperatura"], "temperatura"))
    col_e, col_f, col_g, col_h = st.columns(4)
    col_e.metric("Velocidade", f"{d['velocidade']} km/h", label_alerta(d["velocidade"], "velocidade"))
    col_f.metric("Idade máquina", f"{d['idade_maquina']} anos", label_alerta(d["idade_maquina"], "idade_maquina"))
    col_g.metric("Horas operação", formatar_hhmm(d["horas_operacao"]), label_alerta(d["horas_operacao"], "horas_operacao"))
    col_h.metric("Tipo", d["status_operacao"])

    st.markdown("---")
    _painel_alertas_pendentes(ctx, sessao, equip["id_equipamento"])

    st.markdown("---")
    st.subheader("🔍 Quais variáveis mais influenciam o modelo?")
    st.caption(
        f"Importância global por permutação do modelo {ctx.servico.modelo.versao}: quanto o F1 cai quando a "
        "variável é embaralhada. Para a explicação de uma leitura específica, veja **Por que esse risco?** acima."
    )
    st.bar_chart(ctx.servico.modelo.importancias().set_index("feature"), horizontal=True,
                 color="#2a78d6", sort="-importancia")

    st.markdown("---")
    st.subheader("📅 Últimas predições deste equipamento")
    tab_local, tab_oracle = st.tabs(["💾 SQLite (banco principal)", "🗄️ Oracle XE (opcional)"])
    with tab_local:
        historico = ctx.repo.consultar(
            """SELECT id_predicao, data_hora, usuario, classe_risco, score_risco,
                      prob_baixo, prob_medio, prob_alto, override_aplicado, recomendacao,
                      fonte_clima, fonte_velocidade, fonte_horas, versao_modelo, acao_tomada
               FROM vw_predicoes WHERE id_equipamento = ? ORDER BY data_hora DESC LIMIT 50""",
            [equip["id_equipamento"]],
        )
        if historico.empty:
            st.caption("Nenhuma predição registrada para este equipamento ainda.")
        else:
            tabela(historico, height=320)
    with tab_oracle:
        historico_oracle = _historico_oracle()
        if historico_oracle is not None and len(historico_oracle) > 0:
            st.success(f"✅ Conectado ao Oracle XE. {len(historico_oracle)} predições recentes.")
            tabela(historico_oracle)
        else:
            st.info("ℹ️ Oracle XE não configurado ou indisponível. O SQLite continua registrando tudo.")
