"""Componentes e helpers compartilhados pelas paginas do dashboard."""

from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from agropredict.entrada import STATUS_VALIDOS
from agropredict.fabrica import Contexto, criar_contexto
from agropredict.relatorios import Filtros
from agropredict.seguranca import PERFIS, Sessao

CORES_RISCO = {"BAIXO": "#2C5F2D", "MEDIO": "#E8A33D", "ALTO": "#C8443D"}
EMOJI_RISCO = {"BAIXO": "🟢", "MEDIO": "🟡", "ALTO": "🔴"}
EMOJI_ACAO = {"PENDENTE": "⏳", "RESPEITOU": "✅", "IGNOROU": "❌"}

# Paleta categorica em ordem fixa (cor segue a entidade, nunca o ranking)
PALETA_CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
COR_SERIE_UNICA = PALETA_CATEGORICA[0]


@st.cache_resource(show_spinner="Carregando modelo e banco…")
def contexto() -> Contexto:
    return criar_contexto()


def sessao() -> Sessao:
    return st.session_state["sessao"]


def exigir(recurso: str) -> Sessao:
    """Defesa em profundidade: cada pagina confere a permissao do perfil."""
    s = sessao()
    if not s.pode(recurso):
        contexto().auth.registrar_acesso_negado(s, recurso)
        st.error(f"🚫 O perfil **{PERFIS[s.perfil]}** não tem acesso a esta área.")
        st.stop()
    return s


def cores_para(entidades: list[str], todas: list[str]) -> list[str]:
    """Cor fixa por entidade: a posicao em `todas` (ordenada) define a cor."""
    ordem = sorted(todas)
    return [PALETA_CATEGORICA[ordem.index(e) % len(PALETA_CATEGORICA)] for e in entidades]


def barra_filtros(chave: str, dias_padrao: int = 14, com_status: bool = True) -> Filtros:
    """Filtros em uma unica linha acima dos graficos."""
    equipamentos = contexto().repo.listar_equipamentos()
    regioes = sorted(equipamentos["regiao"].unique())

    colunas = st.columns([2, 2, 2] if com_status else [2, 2])
    hoje = date.today()
    periodo = colunas[0].date_input(
        "Período", value=(hoje - timedelta(days=dias_padrao - 1), hoje), key=f"{chave}_periodo",
        format="DD/MM/YYYY",
    )
    sel_regioes = colunas[1].multiselect("Região", regioes, key=f"{chave}_regioes", placeholder="Todas")
    sel_status = (
        colunas[2].multiselect("Tipo de operação", list(STATUS_VALIDOS), key=f"{chave}_status", placeholder="Todos")
        if com_status else []
    )

    # Enquanto o usuario escolhe o intervalo, o widget devolve so a data inicial
    if isinstance(periodo, (tuple, list)):
        inicio = periodo[0] if periodo else None
        fim = periodo[1] if len(periodo) > 1 else inicio
    else:
        inicio = fim = periodo
    return Filtros(data_inicio=inicio, data_fim=fim, regioes=sel_regioes, status_operacao=sel_status)


def rotulo_classe(classe: str) -> str:
    return f"{EMOJI_RISCO.get(classe, '')} {classe}"


def formatar_hhmm(horas: float) -> str:
    """Converte horas decimais (ex.: 1.5) para 'HH:MM' (ex.: '01:30')."""
    total_min = int(round(max(horas, 0) * 60))
    h, m = divmod(total_min, 60)
    return f"{h:02d}:{m:02d}"


# Cabecalhos legiveis para as colunas vindas do banco (a exportacao CSV mantem os nomes tecnicos)
ROTULOS_COLUNAS = {
    "id_predicao": "Predição", "id_leitura": "Leitura", "id_alerta": "Alerta", "id_rejeicao": "Rejeição",
    "id_equipamento": "Equip. (id)", "data_hora": "Data/hora", "data_emissao": "Emissão", "data_acao": "Respondido em",
    "usuario": "Operador", "operador": "Operador", "usuario_acao": "Respondido por", "perfil": "Perfil",
    "equipamento": "Equipamento", "tipo_equipamento": "Tipo", "modelo": "Modelo", "fabricante": "Fabricante",
    "fazenda": "Fazenda", "regiao": "Região", "status_operacao": "Operação", "operacoes": "Operações",
    "umidade_solo": "Umidade solo (%)", "declividade": "Declividade (%)", "chuva_24h": "Chuva 24h (mm)",
    "temperatura": "Temperatura (°C)", "velocidade": "Velocidade (km/h)", "idade_maquina": "Idade (anos)",
    "horas_operacao": "Horas de operação", "classe_risco": "Classe", "score_risco": "Score",
    "prob_baixo": "P(BAIXO)", "prob_medio": "P(MÉDIO)", "prob_alto": "P(ALTO)", "override_aplicado": "Override",
    "motivo_override": "Motivo do override", "recomendacao": "Recomendação", "versao_modelo": "Modelo",
    "acao_tomada": "Situação", "nivel": "Nível", "nivel_alerta": "Alerta", "categoria": "Categoria",
    "mensagem": "Mensagem", "observacao": "Observação", "fonte_clima": "Fonte clima",
    "fonte_velocidade": "Fonte velocidade", "fonte_horas": "Fonte horas", "idade_anos": "Idade (anos)",
    "horas_medias": "Horas médias", "alertas_mecanicos": "Alertas mecânicos", "mecanicos_alto": "Mecânicos ALTO",
    "ultimo_alerta_mecanico": "Último alerta mecânico", "prioridade": "Prioridade", "alertas": "Alertas",
    "respeitados": "Respeitados", "ignorados": "Ignorados", "pendentes": "Pendentes", "predicoes": "Predições",
    "origem": "Origem", "tipo": "Tipo", "motivo": "Motivo", "dados": "Dados recebidos", "evento": "Evento",
    "sucesso": "Sucesso", "fonte": "Fonte", "manuais": "Manuais", "total": "Total", "cenario": "Cenário",
    "medio": "MÉDIO", "alto": "ALTO", "hora": "Hora", "variavel": "Variável", "ocorrencias": "Ocorrências",
    "faixa": "Faixa",
}


def tabela(df: pd.DataFrame, column_config: dict | None = None, **kwargs) -> None:
    config = {c: st.column_config.Column(ROTULOS_COLUNAS[c]) for c in df.columns if c in ROTULOS_COLUNAS}
    config.update(column_config or {})
    st.dataframe(df, width="stretch", hide_index=True, column_config=config, **kwargs)


def botao_csv(df: pd.DataFrame, nome: str, rotulo: str = "⬇️ Exportar CSV") -> None:
    """Exporta o relatorio exibido (UTF-8 com BOM, abre corretamente no Excel)."""
    st.download_button(
        rotulo, df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{nome}_{date.today().isoformat()}.csv", mime="text/csv", key=f"csv_{nome}",
    )


ROTULO_VARIAVEL = {
    "umidade_solo": ("Umidade do solo", "%"), "declividade": ("Declividade", "%"),
    "chuva_24h": ("Chuva 24h", " mm"), "temperatura": ("Temperatura", " °C"),
    "velocidade": ("Velocidade", " km/h"), "idade_maquina": ("Idade da máquina", " anos"),
    "horas_operacao": ("Horas de operação", " h"),
}


def explicacao_em_texto(explicacao: list[dict], motivo_override: str | None = None) -> list[str]:
    """Frases legiveis para o operador a partir da explicacao local do modelo."""
    linhas = []
    if motivo_override:
        linhas.append(f"⚡ **Regra crítica:** {motivo_override} — risco ALTO independente do modelo.")
    for c in explicacao:
        nome, unidade = ROTULO_VARIAVEL.get(c["variavel"], (c["variavel"], ""))
        linhas.append(
            f"**{nome}** em {c['valor']:g}{unidade} (típico em operação segura: {c['referencia']:g}{unidade}) "
            f"→ **+{c['impacto']:.1f}** pontos no score"
        )
    return linhas or ["Nenhuma variável eleva o risco de forma relevante nesta leitura."]


def emitir_sinal(nivel: str) -> None:
    """Alerta sonoro (Web Audio) e vibracao (Vibration API) no aparelho do operador.

    MEDIO: um bipe curto. ALTO: sequencia de bipes e vibracao. O navegador pode
    bloquear som ate o usuario interagir com a pagina, e a vibracao so existe
    em celulares Android; nesses casos o alerta visual continua valendo.
    """
    bipes = 1 if nivel == "MEDIO" else 5
    frequencia = 660 if nivel == "MEDIO" else 880
    vibracao = "[200]" if nivel == "MEDIO" else "[400, 150, 400, 150, 400]"
    components.html(
        f"""<script>
        // {nivel} {time.time()}
        try {{
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          ctx.resume();
          for (let i = 0; i < {bipes}; i++) {{
            const osc = ctx.createOscillator(), ganho = ctx.createGain();
            osc.frequency.value = {frequencia};
            ganho.gain.value = 0.2;
            osc.connect(ganho); ganho.connect(ctx.destination);
            osc.start(ctx.currentTime + i * 0.4);
            osc.stop(ctx.currentTime + i * 0.4 + 0.25);
          }}
          if (navigator.vibrate) navigator.vibrate({vibracao});
        }} catch (e) {{}}
        </script>""",
        height=0,
    )
