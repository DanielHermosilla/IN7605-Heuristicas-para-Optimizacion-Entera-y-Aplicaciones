$ErrorActionPreference = "Stop"

if (-not (Test-Path "heuristicas")) {
  python -m venv heuristicas
}

# Activar
$activate = ".\heuristicas\Scripts\Activate.ps1"
. $activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m ipykernel install --user --name heuristicas --display-name "Python (heuristicas)"

Write-Host @"
Listo ✅
- Venv activado: heuristicas
- Dependencias instaladas desde requirements.txt
- Kernel registrado: Python (heuristicas)

Para activar manualmente más tarde:
  .\heuristicas\Scripts\Activate.ps1
"@
