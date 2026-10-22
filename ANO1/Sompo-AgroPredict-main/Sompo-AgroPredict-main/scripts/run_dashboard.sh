#!/usr/bin/env bash
# =====================================================================
# Sompo AgroPredict - inicializacao do dashboard (Linux / macOS)
# ---------------------------------------------------------------------
# Uso, a partir da raiz do repositorio:
#     bash scripts/run_dashboard.sh
#
# As credenciais do Oracle sao OPCIONAIS: sem elas, o dashboard grava
# apenas na tabela SQLite local e continua funcionando normalmente.
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$RAIZ/src/dashboard/app.py"

if [ ! -f "$APP" ]; then
  echo "app.py nao encontrado em $APP" >&2
  exit 1
fi

echo "Iniciando Sompo AgroPredict em http://localhost:8501 ..."
streamlit run "$APP"
