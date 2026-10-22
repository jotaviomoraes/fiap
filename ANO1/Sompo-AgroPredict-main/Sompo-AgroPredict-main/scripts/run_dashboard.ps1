# =====================================================================
# Sompo AgroPredict - inicializacao do dashboard (Windows / PowerShell)
# ---------------------------------------------------------------------
# Uso, a partir da raiz do repositorio:
#     .\scripts\run_dashboard.ps1
#
# As credenciais do Oracle sao OPCIONAIS: sem elas, o dashboard grava
# apenas na tabela SQLite local e continua funcionando normalmente.
# =====================================================================

$raiz = Split-Path -Parent $PSScriptRoot
$app  = Join-Path $raiz "src\dashboard\app.py"

if (-not (Test-Path $app)) {
    Write-Error "app.py nao encontrado em $app"
    exit 1
}

Write-Host "Iniciando Sompo AgroPredict em http://localhost:8501 ..."
streamlit run $app
