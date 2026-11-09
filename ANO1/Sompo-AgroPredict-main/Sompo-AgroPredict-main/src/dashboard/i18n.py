"""Internacionalizacao do dashboard (Portugues, Ingles e Espanhol).

O portugues e a lingua de origem: as strings em PT sao usadas como chave
nos catalogos de traducao. Assim, qualquer texto novo continua funcionando
em PT mesmo antes de receber traducao, e o teste `tests/test_i18n.py`
garante que os catalogos EN/ES estao completos.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

IDIOMAS = {"pt": "Português", "en": "English", "es": "Español"}
BANDEIRAS = {"pt": "🇧🇷", "en": "🇺🇸", "es": "🇪🇸"}
_IDIOMA_PADRAO = (os.getenv("APP_LANG") or "pt").lower()
if _IDIOMA_PADRAO not in IDIOMAS:
    _IDIOMA_PADRAO = "pt"

# ---------------------------------------------------------------------
# Catalogos
# ---------------------------------------------------------------------
# `traducoes.CATALOGO` guarda as tuplas (pt, en, es) das strings de tela.
# A chave e sempre o texto em portugues, entao textos novos continuam
# aparecendo em PT mesmo antes de serem traduzidos.
try:  # importado como pacote (tests) ou com src/dashboard no sys.path (Streamlit)
    from .traducoes import CATALOGO
except ImportError:
    from traducoes import CATALOGO

TRADUCOES: dict[str, dict[str, str]] = {
    "en": {pt: en for pt, en, _es in CATALOGO},
    "es": {pt: es for pt, _en, es in CATALOGO},
}

# Valores de dominio: o banco guarda sempre o valor em portugues.
CLASSES = {"BAIXO": ("LOW", "BAJO"), "MEDIO": ("MEDIUM", "MEDIO"), "ALTO": ("HIGH", "ALTO")}
STATUS = {"Colheita": ("Harvest", "Cosecha"), "Deslocamento": ("Travel", "Desplazamiento"),
          "Manobra": ("Maneuver", "Maniobra")}
ACOES = {"PENDENTE": ("PENDING", "PENDIENTE"), "RESPEITOU": ("FOLLOWED", "RESPETÓ"),
         "IGNOROU": ("IGNORED", "IGNORÓ")}
PRIORIDADES = {"ALTA": ("HIGH", "ALTA"), "MEDIA": ("MEDIUM", "MEDIA"), "BAIXA": ("LOW", "BAJA")}
CATEGORIAS = {"climatico": ("climate", "climático"), "operacional": ("operational", "operacional"),
              "mecanico": ("mechanical", "mecánico")}
FAIXAS = {"Excelente": ("Excellent", "Excelente"), "Bom": ("Good", "Bueno"),
          "Atenção": ("Attention", "Atención"), "Crítico": ("Critical", "Crítico"),
          "Dados insuficientes": ("Insufficient data", "Datos insuficientes")}
PERFIS = {"operador": ("Field operator", "Operador de campo"),
          "gestor": ("Fleet manager", "Gestor de flota"),
          "tecnico": ("Maintenance technician", "Técnico de mantenimiento"),
          "analista": ("Analyst João", "Analista João"),
          "admin": ("Administrator", "Administrador")}
FONTES = {
    "manual": ("manual", "manual"), "open-meteo": ("open-meteo", "open-meteo"),
    "simulado": ("simulated", "simulado"), "cadastro": ("registration", "registro"),
    "gps_auto": ("GPS (auto)", "GPS (auto)"), "pausado": ("paused", "pausado"),
    "gps_chip": ("GPS chip", "chip GPS"), "calculada": ("calculated", "calculada"),
    "indisponivel": ("unavailable", "no disponible"), "operador": ("operator", "operador"),
    "sistema": ("system", "sistema"),
}
TIPOS_REJEICAO = {"INVALIDA": ("INVALID", "INVÁLIDA"), "DUPLICADA": ("DUPLICATE", "DUPLICADA")}
ORIGENS = {"dashboard": ("dashboard", "dashboard"), "simulador": ("simulator", "simulador"),
           "validacao-lote": ("validation batch", "lote de validación"),
           "validacao-corrupcao": ("corruption test", "prueba de corrupción")}
PAGINAS = {"operacao": ("operation", "operación"), "frota": ("fleet", "flota"),
           "alertas": ("alerts", "alertas"), "manutencao": ("maintenance", "mantenimiento"),
           "auditoria": ("audit", "auditoría")}
EVENTOS = {"login": ("login", "inicio de sesión"), "logout": ("logout", "cierre de sesión"),
           "login_bloqueado": ("blocked login", "inicio de sesión bloqueado")}

VARIAVEIS = {
    "umidade_solo": ("soil moisture", "humedad del suelo"),
    "declividade": ("slope", "pendiente"),
    "chuva_24h": ("24h rainfall", "lluvia 24h"),
    "temperatura": ("temperature", "temperatura"),
    "velocidade": ("speed", "velocidad"),
    "idade_maquina": ("machine age", "edad de la máquina"),
    "horas_operacao": ("operating hours", "horas de operación"),
    "status_operacao": ("operation type", "tipo de operación"),
}

RECOMENDACOES = {
    "Seguir rota atual": ("Follow current route", "Seguir la ruta actual"),
    "Risco de atolamento — evitar areas saturadas": (
        "Stuck risk — avoid saturated areas", "Riesgo de atascamiento — evitar áreas saturadas"),
    "Atencao a inclinacao — reduzir velocidade imediatamente": (
        "Watch the slope — reduce speed immediately", "Atención a la pendiente — reducir la velocidad de inmediato"),
    "Chuva intensa — suspender operacao": (
        "Heavy rain — suspend operation", "Lluvia intensa — suspender la operación"),
    "Pausa obrigatoria — risco de fadiga e superaquecimento": (
        "Mandatory break — fatigue and overheating risk", "Pausa obligatoria — riesgo de fatiga y sobrecalentamiento"),
    "Velocidade critica — reduzir imediatamente": (
        "Critical speed — reduce immediately", "Velocidad crítica — reducir de inmediato"),
    "Verificar equipamento — desgaste elevado": (
        "Check the equipment — high wear", "Verificar el equipo — desgaste elevado"),
    "Interromper operacao": ("Stop operation", "Interrumpir la operación"),
    "Reduzir velocidade e monitorar": ("Reduce speed and monitor", "Reducir la velocidad y monitorear"),
}

COLUNAS_CATEGORICAS = {
    "classe_risco": "classes", "classe_modelo": "classes", "nivel": "classes", "nivel_alerta": "classes",
    "status_operacao": "status", "acao_tomada": "acoes", "prioridade": "prioridades",
    "categoria": "categorias", "categoria_alerta": "categorias", "faixa": "faixas",
    "perfil": "perfis", "evento": "eventos", "tipo": "tipos_rejeicao", "origem": "origens",
    "fonte": "fontes", "fonte_umidade": "fontes", "fonte_clima": "fontes",
    "fonte_velocidade": "fontes", "fonte_horas": "fontes", "fonte_idade": "fontes",
    "variavel": "variaveis",
}

_MAPAS = {
    "classes": CLASSES, "status": STATUS, "acoes": ACOES, "prioridades": PRIORIDADES,
    "categorias": CATEGORIAS, "faixas": FAIXAS, "perfis": PERFIS, "fontes": FONTES,
    "tipos_rejeicao": TIPOS_REJEICAO, "origens": ORIGENS, "eventos": EVENTOS,
    "paginas": PAGINAS, "variaveis": VARIAVEIS,
}


def idioma_atual() -> str:
    """Idioma ativo, persistido na sessao e no parametro `?lang=`."""
    try:
        lang = st.session_state.get("idioma")
        if lang not in IDIOMAS:
            lang = st.query_params.get("lang", _IDIOMA_PADRAO)
            if isinstance(lang, list):
                lang = lang[0] if lang else _IDIOMA_PADRAO
            lang = (lang or _IDIOMA_PADRAO).lower()
            if lang not in IDIOMAS:
                lang = _IDIOMA_PADRAO
            st.session_state["idioma"] = lang
        return lang
    except Exception:
        return _IDIOMA_PADRAO


def _trocar_idioma() -> None:
    lang = st.session_state.get("_idioma_select", _IDIOMA_PADRAO)
    if lang not in IDIOMAS:
        lang = _IDIOMA_PADRAO
    st.session_state["idioma"] = lang
    try:
        st.query_params["lang"] = lang
    except Exception:
        pass


def seletor_idioma() -> None:
    """Seletor compacto na sidebar. Pode ser chamado antes do login."""
    try:
        if "_idioma_select" not in st.session_state:
            st.session_state["_idioma_select"] = idioma_atual()
        st.sidebar.selectbox(
            t("Idioma"), list(IDIOMAS), key="_idioma_select", on_change=_trocar_idioma,
            format_func=lambda k: f"{BANDEIRAS.get(k, '')} {IDIOMAS[k]}",
        )
    except Exception:
        pass


def t(texto: str, **kwargs) -> str:
    """Traduz uma string em portugues para o idioma ativo."""
    lang = idioma_atual()
    saida = TRADUCOES.get(lang, {}).get(texto, texto) if lang != "pt" else texto
    try:
        return saida.format(**kwargs) if kwargs else saida
    except (KeyError, IndexError):
        return saida


# ---------------------------------------------------------------------
# Valores de dominio
# ---------------------------------------------------------------------
def _tr_mapa(categoria: str, valor):
    if valor is None:
        return valor
    mapa = _MAPAS.get(categoria, {})
    par = mapa.get(str(valor))
    if not par:
        return valor
    return par[0] if idioma_atual() == "en" else par[1] if idioma_atual() == "es" else valor


def tr_classe(valor): return _tr_mapa("classes", valor)
def tr_status(valor): return _tr_mapa("status", valor)
def tr_acao(valor): return _tr_mapa("acoes", valor)
def tr_prioridade(valor): return _tr_mapa("prioridades", valor)
def tr_categoria(valor): return _tr_mapa("categorias", valor)
def tr_faixa(valor): return _tr_mapa("faixas", valor)
def tr_perfil(valor): return _tr_mapa("perfis", valor)
def tr_fonte(valor): return _tr_mapa("fontes", valor)
def tr_origem(valor): return _tr_mapa("origens", valor)
def tr_pagina(valor): return _tr_mapa("paginas", valor)
def tr_variavel(valor): return _tr_mapa("variaveis", valor)


def tr_evento(evento):
    if not isinstance(evento, str):
        return evento
    if evento.startswith("negado:"):
        recurso = evento.split(":", 1)[1]
        if idioma_atual() == "en":
            return f"denied:{tr_pagina(recurso)}"
        if idioma_atual() == "es":
            return f"denegado:{tr_pagina(recurso)}"
        return evento
    return _tr_mapa("eventos", evento)


def tr_recomendacao(texto):
    if not isinstance(texto, str):
        return texto
    par = RECOMENDACOES.get(texto)
    if not par:
        return texto
    return par[0] if idioma_atual() == "en" else par[1] if idioma_atual() == "es" else texto


def tr_lista_variaveis(texto):
    if not isinstance(texto, str):
        return texto
    return ", ".join(tr_variavel(v.strip()) for v in texto.split(",") if v.strip())


def tr_motivo_override(texto):
    if not isinstance(texto, str):
        return texto
    m = re.match(r"^Variavel\(is\) no limite maximo: (.+)$", texto)
    if not m:
        return texto
    variaveis = tr_lista_variaveis(m.group(1))
    if idioma_atual() == "en":
        return f"Variable(s) at the maximum limit: {variaveis}"
    if idioma_atual() == "es":
        return f"Variable(s) en el límite máximo: {variaveis}"
    return texto


def tr_motivo_rejeicao(texto):
    """Traduz os motivos gerados por `Leitura.de_dict` e pelo servico."""
    if not isinstance(texto, str):
        return texto
    lang = idioma_atual()
    if lang == "pt":
        return texto
    partes = []
    for parte in texto.split(";"):
        parte = parte.strip()
        m = re.match(r"^(\w+) ausente$", parte)
        if m:
            partes.append(f"{tr_variavel(m.group(1))} missing" if lang == "en"
                          else f"{tr_variavel(m.group(1))} ausente")
            continue
        m = re.match(r"^(\w+) nao numerico \((.+)\)$", parte)
        if m:
            partes.append(f"{tr_variavel(m.group(1))} not numeric ({m.group(2)})" if lang == "en"
                          else f"{tr_variavel(m.group(1))} no numérico ({m.group(2)})")
            continue
        m = re.match(r"^(\w+) invalido \((.+)\)$", parte)
        if m:
            partes.append(f"{tr_variavel(m.group(1))} invalid ({m.group(2)})" if lang == "en"
                          else f"{tr_variavel(m.group(1))} inválido ({m.group(2)})")
            continue
        m = re.match(r"^(\w+)=(.+) fora da faixa \[(.+), (.+)\]$", parte)
        if m:
            partes.append(f"{tr_variavel(m.group(1))}={m.group(2)} out of range [{m.group(3)}, {m.group(4)}]"
                          if lang == "en" else
                          f"{tr_variavel(m.group(1))}={m.group(2)} fuera de rango [{m.group(3)}, {m.group(4)}]")
            continue
        m = re.match(r"^status_operacao invalido \((.+)\)$", parte)
        if m:
            partes.append(f"operation type invalid ({m.group(1)})" if lang == "en"
                          else f"tipo de operación inválido ({m.group(1)})")
            continue
        m = re.match(r"^identica a leitura #(\d+)$", parte)
        if m:
            partes.append(f"identical to reading #{m.group(1)}" if lang == "en"
                          else f"idéntica a la lectura #{m.group(1)}")
            continue
        m = re.match(r"^equipamento (\d+) nao cadastrado$", parte)
        if m:
            partes.append(f"equipment {m.group(1)} not registered" if lang == "en"
                          else f"equipo {m.group(1)} no registrado")
            continue
        if parte == "integridade violada: a leitura foi alterada depois de gravada":
            partes.append("integrity violation: the reading was changed after being stored" if lang == "en"
                          else "integridad violada: la lectura fue alterada después de guardarse")
            continue
        partes.append(parte)
    return "; ".join(partes)


# ---------------------------------------------------------------------
# Formatacao
# ---------------------------------------------------------------------
def formatar_numero(valor, casas: int = 0) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    texto = f"{numero:,.{casas}f}"
    if idioma_atual() in {"pt", "es"}:
        texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return texto


def formatar_data(valor, com_hora: bool = False) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.replace("T", " "))
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        fmt = "%m/%d/%Y" if idioma_atual() == "en" else "%d/%m/%Y"
        if com_hora:
            fmt += " %H:%M"
        return valor.strftime(fmt)
    if isinstance(valor, date):
        return valor.strftime("%m/%d/%Y" if idioma_atual() == "en" else "%d/%m/%Y")
    return str(valor)


def formato_data_input() -> str:
    return "MM/DD/YYYY" if idioma_atual() == "en" else "DD/MM/YYYY"


# ---------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------
def traduzir_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for coluna in out.columns:
        if coluna in COLUNAS_CATEGORICAS:
            categoria = COLUNAS_CATEGORICAS[coluna]
            out[coluna] = out[coluna].map(lambda v: _tr_mapa(categoria, v))
        elif coluna in {"recomendacao", "mensagem", "cenario"}:
            out[coluna] = out[coluna].map(tr_recomendacao)
        elif coluna == "motivo_override":
            out[coluna] = out[coluna].map(tr_motivo_override)
        elif coluna == "variaveis_alerta":
            out[coluna] = out[coluna].map(tr_lista_variaveis)
        elif coluna == "motivo":
            out[coluna] = out[coluna].map(tr_motivo_rejeicao)
        elif coluna == "evento":
            out[coluna] = out[coluna].map(tr_evento)
        elif coluna in {"data_hora", "data_emissao", "data_acao", "ultimo_alerta_mecanico", "criado_em"}:
            out[coluna] = out[coluna].map(lambda v: formatar_data(v, com_hora=True))
    return out
