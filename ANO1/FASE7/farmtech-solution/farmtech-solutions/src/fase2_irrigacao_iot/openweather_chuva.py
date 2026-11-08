"""
FarmTech Solutions - Fase 2 - Ir Alem 1
Consulta previsao de chuva no OpenWeather para Sorriso/MT
e imprime o valor para colar no Serial Monitor do Wokwi.

Uso: pip install requests && python openweather_chuva.py
(chave em OPENWEATHER_API_KEY no .env da raiz)
"""

import os
import sys
from datetime import datetime, timedelta

import requests

# Carrega o arquivo .env da raiz do projeto, se o python-dotenv estiver instalado
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.getenv("OPENWEATHER_API_KEY", "sua_api_key_aqui")  # definida no .env
CIDADE = "Sorriso,BR"
URL = "https://api.openweathermap.org/data/2.5/forecast"
FUSO_HORARIO = -3  # GMT-3 (horario de Brasilia)


def converter_horario(dt_utc_str):
    """Converte string UTC ('2026-04-17 03:00:00') para horario local GMT-3."""
    dt_utc = datetime.strptime(dt_utc_str, "%Y-%m-%d %H:%M:%S")
    dt_local = dt_utc + timedelta(hours=FUSO_HORARIO)
    return dt_local.strftime("%d/%m %H:%M")


def main():
    print("FarmTech - Previsao de Chuva (Milho - Sorriso/MT)")
    print(f"Horarios em GMT{FUSO_HORARIO} (Brasilia)")
    print("-" * 50)

    try:
        resp = requests.get(URL, params={
            "q": CIDADE,
            "appid": API_KEY,
            "units": "metric",
            "lang": "pt_br"
        }, timeout=10)
    except requests.RequestException:
        print("Nao foi possivel consultar a previsao. Verifique a conexao com a internet.")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Erro {resp.status_code}: verifique sua API key")
        sys.exit(1)

    dados = resp.json()
    blocos = dados["list"][:2]  # proximas 6h (2 blocos de 3h)

    total = 0.0
    for b in blocos:
        chuva = b.get("rain", {}).get("3h", 0.0)
        total += chuva
        horario_local = converter_horario(b["dt_txt"])
        print(f"  {horario_local} | {b['weather'][0]['description']:20s} | chuva: {chuva}mm")

    print("-" * 50)
    print(f"Chuva total prevista (6h): {total:.1f} mm")
    print(f">>> Cole no Serial Monitor do Wokwi: {total:.1f}")

    if total >= 5.0:
        print(">>> ESP32 ira SUSPENDER irrigacao")
    else:
        print(">>> ESP32 decide com base nos sensores")


if __name__ == "__main__":
    main()