"""
gps.py
------
Captura localizacao e velocidade em tempo real a partir do GPS do celular
do operador, usando a Geolocation API do proprio navegador (funciona no
Chrome/Safari mobile quando o operador abre o dashboard no celular).

Requer: pip install streamlit-js-eval

Este modulo so conversa com o navegador. O calculo da velocidade (chip
GPS ou Haversine entre duas leituras) e o descarte de leituras
incoerentes ficam em `agropredict.telemetria`, testado sem interface.
"""

from __future__ import annotations

import time

import streamlit as st
from streamlit_js_eval import get_geolocation

from agropredict.telemetria import calcular_velocidade_kmh


def capturar_posicao(ciclo: int | str = 0) -> dict | None:
    """
    Dispara o prompt de permissao de localizacao no navegador (na primeira
    vez) e retorna a leitura mais recente.

    IMPORTANTE: `get_geolocation()` do streamlit-js-eval usa por padrao uma
    key FIXA ("getLocation()"). Como componentes do Streamlit so reexecutam
    o JS quando a key muda, sem variar `ciclo` a cada rerun a leitura fica
    travada na primeira posicao para sempre -- e por isso a velocidade
    calculada nunca avancava (sempre so 1 ponto disponivel).

    Passe aqui o contador do st_autorefresh (ou qualquer valor que mude a
    cada rerun) para forcar uma nova leitura de GPS em cada ciclo.

    Retorna None se o navegador ainda nao respondeu, o usuario negou ou a
    resposta veio sem coordenadas validas.
    """
    loc = get_geolocation(component_key=f"geo_{ciclo}")
    if not isinstance(loc, dict) or not isinstance(loc.get("coords"), dict):
        return None

    coords = loc["coords"]
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    timestamp = loc.get("timestamp")
    return {
        "lat": lat,
        "lon": lon,
        "accuracy_m": coords.get("accuracy"),
        "speed_ms": coords.get("speed"),  # pode ser None
        "timestamp": (timestamp / 1000) if isinstance(timestamp, (int, float)) else time.time(),
    }


def obter_velocidade_kmh(posicao_atual: dict | None) -> tuple[float | None, str]:
    """
    Retorna (velocidade_kmh, origem) onde origem in {"gps_chip", "calculada", "indisponivel"}.
    Guarda a ultima posicao em st.session_state["_ultima_posicao"] para o calculo por Haversine.
    """
    anterior = st.session_state.get("_ultima_posicao")
    velocidade, origem = calcular_velocidade_kmh(posicao_atual, anterior)
    if posicao_atual is not None:
        st.session_state["_ultima_posicao"] = posicao_atual
    return velocidade, origem
