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
from threadpoolctl import threadpool_limits

from agropredict.clima import buscar_clima_atual
from agropredict.config import config_oracle
from agropredict.entrada import Leitura, LeituraInvalida, STATUS_VALIDOS
from agropredict.oracle import configurado as oracle_configurado
from agropredict.regras import ALERTA, MAXIMO
from agropredict.relatorios import Filtros
from agropredict.servico import ErroProcessamento, LeituraDuplicada
from gps import capturar_posicao, obter_velocidade_kmh
from i18n import formatar_numero, t, tr_classe, tr_motivo_override, tr_recomendacao, tr_status
from tema import cartao_risco, status_risco_lateral
from ui_comum import (
    EMOJI_ACAO, EMOJI_RISCO, contexto, emitir_sinal, exigir, explicacao_em_texto, formatar_hhmm,
    rotulo_classe, tabela,
)

INTERVALO_MIN_GRAVACAO = 10  # segundos — limite entre gravacoes, sem agendar atualizacoes


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
    try:
        config = config_oracle()
        if not oracle_configurado(config):
            return None
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


def _campo_telemetria(
    rotulo, chave, minimo, maximo, padrao, *, automatico=None, ajuda=None, passo=None,
):
    if automatico is not None:
        st.number_input(rotulo, value=automatico, disabled=True, help=ajuda)
        return automatico
    return st.number_input(rotulo, minimo, maximo, padrao, step=passo, key=chave, help=ajuda)


def _entradas(ctx):
    """Coleta as 8 features + equipamento + origem de cada dado."""
    equipamentos = ctx.repo.listar_equipamentos()
    rotulos = {
        int(r.id_equipamento): f"{r.codigo} · {r.tipo} {r.modelo} ({r.regiao})"
        for r in equipamentos.itertuples()
    }
    maquina, tipo = st.columns(2, gap="small")
    id_equipamento = maquina.selectbox(
        t("Equipamento em operação"), list(rotulos), format_func=rotulos.get, key="op_equipamento"
    )
    status_operacao = tipo.selectbox(t("Tipo de operação"), list(STATUS_VALIDOS), format_func=tr_status)
    equip = ctx.repo.obter_equipamento(id_equipamento)

    modo_real = st.toggle(
        t("📡 Usar GPS + clima em tempo real"), value=True, key="op_modo_real",
        help=t("Desative para digitar tudo manualmente (modo demo/offline)."),
    )
    status = st.container()
    with st.container(horizontal=True, gap="small"):
        if modo_real and st.button(t("🔄 Atualizar GPS"), key="atualizar_gps"):
            st.session_state["_ciclo_gps"] = st.session_state.get("_ciclo_gps", 0) + 1
        if modo_real and st.button(t("🔄 Reiniciar contador de horas"), key="op_reiniciar_horas"):
            st.session_state["_horas_acumuladas"] = 0.0
            st.session_state.pop("_ultimo_tick_horas", None)

    ciclo = st.session_state.get("_ciclo_gps", 0)
    with st.expander(t("✍️ Substituir algum campo manualmente")):
        st.caption(t("Marque se o sensor correspondente não conectou hoje."))
        manual_velocidade = st.checkbox(t("Velocidade"), key="manual_velocidade", disabled=not modo_real)
        manual_clima = st.checkbox(t("Temperatura / Chuva"), key="manual_clima", disabled=not modo_real)
        manual_umidade = st.checkbox(t("Umidade do solo"), key="manual_umidade", disabled=not modo_real)
        manual_horas = st.checkbox(t("Horas de operação"), key="manual_horas", disabled=not modo_real)
        manual_idade = st.checkbox(t("Idade da máquina"), key="manual_idade", disabled=not modo_real)

    posicao = capturar_posicao(ciclo) if modo_real else None
    velocidade_gps, origem_velocidade = obter_velocidade_kmh(posicao) if modo_real else (None, "indisponivel")
    clima = _clima(posicao["lat"], posicao["lon"]) if posicao and posicao.get("lat") is not None else None

    with status:
        if modo_real:
            if posicao is None:
                st.warning(t("Aguardando permissão de localização do navegador…"))
            else:
                st.caption(
                    t("GPS: {lat}, {lon} (±{acc}m) · leitura #{ciclo}",
                      lat=f"{posicao['lat']:.5f}", lon=f"{posicao['lon']:.5f}",
                      acc=posicao.get("accuracy_m", "?"), ciclo=ciclo)
                )
            if clima and clima["ok"]:
                st.caption(t("Clima: Open-Meteo · atualizado agora"))
            elif clima:
                st.error(t("Falha na API de clima: {erro}", erro=clima.get("erro", "")))
            if not manual_velocidade and velocidade_gps is None:
                st.caption(t("⏳ Aguardando 2ª leitura de GPS para calcular velocidade…"))
        else:
            st.caption(t("Modo manual — sem captura em tempo real."))

    # O contador soma apenas enquanto o GPS está conectado e as horas são automáticas.
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

    umidade_clima = clima.get("umidade_solo") if clima else None
    umidade_auto = None if manual_umidade else umidade_clima
    clima_auto = clima if clima and clima["ok"] and not manual_clima else None
    velocidade_auto = None if manual_velocidade else velocidade_gps
    idade_cadastro = max(0, date.today().year - int(equip["ano_fabricacao"]))
    idade_auto = idade_cadastro if modo_real and not manual_idade else None
    horas_auto = (
        round(min(st.session_state["_horas_acumuladas"], 14.0), 2)
        if modo_real and not manual_horas else None
    )

    fonte_umidade = "open-meteo" if umidade_auto is not None else "manual"
    fonte_clima = "open-meteo" if clima_auto else "manual"
    fonte_velocidade = origem_velocidade if velocidade_auto is not None else "manual"
    fonte_idade = "cadastro" if idade_auto is not None else "manual"
    fonte_horas = ("gps_auto" if contando else "pausado") if horas_auto is not None else "manual"

    with st.container(key="agro_medicoes"):
        umidade_solo = _campo_telemetria(
            t("Umidade do solo (%)"), "op_umidade", 0, 100,
            int(umidade_clima) if umidade_clima is not None else 20,
            automatico=umidade_auto, ajuda="Open-Meteo" if umidade_auto is not None else None,
        )
        declividade = st.number_input(
            t("Declividade (%)"), 0, 25, 8, key="op_declividade",
            help=t("Ainda depende de mapa GIS/satélite por talhão — não coberto pelo GPS do celular."),
        )
        chuva_24h = _campo_telemetria(
            t("Chuva 24h (mm)"), "op_chuva", 0, 40, 4,
            automatico=clima_auto["chuva_24h"] if clima_auto else None,
            ajuda="Open-Meteo" if clima_auto else None,
        )
        temperatura = _campo_telemetria(
            t("Temperatura (°C)"), "op_temperatura", 15, 45, 26,
            automatico=clima_auto["temperatura"] if clima_auto else None,
            ajuda="Open-Meteo" if clima_auto else None,
        )
        velocidade = _campo_telemetria(
            t("Velocidade (km/h)"), "op_velocidade", 0, 20, 7,
            automatico=velocidade_auto, ajuda=t(origem_velocidade) if velocidade_auto is not None else None,
        )
        idade_maquina = _campo_telemetria(
            t("Idade da máquina (anos)"), f"op_idade_{id_equipamento}", 0, 20, min(idade_cadastro, 20),
            automatico=idade_auto, ajuda=t("fabricação {ano}", ano=equip["ano_fabricacao"]),
        )
        horas_operacao = _campo_telemetria(
            t("Horas de operação"), "op_horas", 0.0, 14.0, 5.0,
            automatico=horas_auto, ajuda=t(fonte_horas) if horas_auto is not None else None, passo=0.1,
        )

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
    st.title(t("Operação em tempo real"))
    equipamento_info = st.empty()
    with st.container(key="agro_operacao"):
        painel, entrada = st.columns([1.45, 1], gap="medium")
        with entrada:
            telemetria = st.container(border=True, key="agro_telemetria")
        with telemetria:
            st.subheader(t("Equipamento e telemetria"))
            equip, modo_real, dados, fontes, posicao = _entradas(ctx)
            som_ativo = st.toggle(
                t("🔊 Alerta sonoro e vibração"), value=True, key="op_som",
                help=t("Sinal curto ao entrar em MÉDIO; sinal repetido e vibração em ALTO."),
            )

    equipamento_info.caption(
        f"{equip['codigo']} · {equip['tipo']} {equip['fabricante']} {equip['modelo']} · "
        f"{equip['fazenda']} · {equip['regiao']}"
    )
    avisos = painel.container()

    # ------------------------------------------------------------------
    # Previa (sem gravar) — mesma funcao de avaliacao usada na gravacao
    # ------------------------------------------------------------------
    try:
        # O limite deve valer na thread do Streamlit, inclusive quando o
        # contexto ainda guarda uma instancia criada antes de um deploy.
        with threadpool_limits(limits=1):
            _, avaliacao = _avaliar_previa(ctx, dados)
    except LeituraInvalida as exc:
        st.session_state.pop("_agro_risco_operacao", None)
        with avisos:
            st.error(t("❌ Leitura rejeitada pela validação de entrada — nada foi gravado."))
            for problema in exc.problemas:
                from i18n import tr_motivo_rejeicao
                st.markdown(f"- {tr_motivo_rejeicao(problema)}")
            st.info(t("Use **Substituir algum campo manualmente** no painel de telemetria para corrigir o dado."))
        st.stop()

    # ------------------------------------------------------------------
    # Persistencia: entrada -> banco -> modelo -> saida, pelo servico
    # ------------------------------------------------------------------
    # Gravacao automatica so com GPS conectado: sem sinal, os campos padrao
    # nao devem virar leituras "reais" no banco a cada ciclo.
    agora_ts = time.time()
    telemetria_ativa = modo_real and posicao is not None
    gravar_auto = (
        telemetria_ativa and agora_ts - st.session_state.get("_ultimo_save", 0) >= INTERVALO_MIN_GRAVACAO
    )
    gravar_manual = (
        telemetria.button(t("Avaliar e registrar"), key="op_registrar", type="primary", width="stretch")
        if not telemetria_ativa else False
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
            avisos.info(t("ℹ️ Leitura idêntica à #{id} já registrada — não foi gravada de novo.", id=exc.id_existente))
        except (ErroProcessamento, ValueError) as exc:
            avisos.error(t("❌ Falha ao registrar a leitura: {erro}", erro=exc))

    # ------------------------------------------------------------------
    # Saida
    # ------------------------------------------------------------------
    ultimo = st.session_state.get("_ultimo_resultado")
    with avisos:
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
            st.info(t("Prévia — ainda não gravada. Use **Avaliar e registrar** no painel de telemetria."))

    classe = avaliacao.classe_risco
    st.session_state["_agro_risco_operacao"] = (classe, str(equip["codigo"]))
    status_risco_lateral()
    # US-01: sinal curto na transicao para MEDIO; sinal repetido + vibracao a cada ciclo em ALTO
    anterior = st.session_state.get("_classe_sinalizada")
    if som_ativo and (classe == "ALTO" or (classe == "MEDIO" and anterior != "MEDIO")):
        emitir_sinal(classe)
    st.session_state["_classe_sinalizada"] = classe

    with painel:
        cartao_risco(avaliacao)
        with st.container(border=True, key="agro_alertas"):
            _painel_alertas_pendentes(ctx, sessao, equip["id_equipamento"])
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

    probabilidade, contexto_leitura = st.columns(2)
    with probabilidade.container(border=True, key="agro_probabilidades"):
        st.markdown(t("### Probabilidades"))
        for c in ("BAIXO", "MEDIO", "ALTO"):
            p = avaliacao.prob(c)
            st.markdown(f"**{rotulo_classe(c)}**")
            st.progress(float(p))
            st.caption(f"{p * 100:.1f}%")

    with contexto_leitura.container(border=True, key="agro_contexto"):
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
            if st.button(t("Consultar réplica Oracle"), key="consultar_replica_oracle"):
                historico_oracle = _historico_oracle()
                if historico_oracle is not None and len(historico_oracle) > 0:
                    st.success(t("✅ Conectado ao Oracle. {n} predições recentes.", n=len(historico_oracle)))
                    tabela(historico_oracle)
                else:
                    st.info(t("ℹ️ Oracle não configurado ou indisponível. O SQLite continua registrando tudo."))
