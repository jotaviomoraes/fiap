$ErrorActionPreference = 'Stop'
$pythonFase7 = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonFase7)) {
    throw 'Ambiente local não encontrado. Siga README_LOCAL.md para instalar.'
}
& $pythonFase7 -m ipykernel install --prefix (Join-Path $PSScriptRoot '.venv') --name fase7 --display-name 'Python (FASE7)'
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível registrar o kernel local.' }
& $pythonFase7 -m jupyterlab $PSScriptRoot
