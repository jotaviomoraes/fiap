# =====================================================================
# AgroPredict - inicializacao do dashboard (Windows / PowerShell)
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

Write-Host "Iniciando AgroPredict em http://localhost:8501 ..."
$pythonDashboard = "python"
$pythonAtivo = if ($env:VIRTUAL_ENV) { Join-Path $env:VIRTUAL_ENV "Scripts\python.exe" } else { $null }
$ano1Dashboard = Split-Path -Parent (Split-Path -Parent $raiz)
$pythonCudaDashboard = Join-Path $ano1Dashboard "FASE7\.venv\Scripts\python.exe"
if ($pythonAtivo -and (Test-Path -LiteralPath $pythonAtivo)) {
    $pythonDashboard = $pythonAtivo
} elseif (Test-Path -LiteralPath $pythonCudaDashboard) {
    $pythonDashboard = $pythonCudaDashboard
}
& $pythonDashboard -m streamlit run $app
