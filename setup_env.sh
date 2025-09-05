#!/usr/bin/env bash
set -euo pipefail

# Crea (si no existe) y activa el venv llamado "heuristicas"
if [ ! -d "heuristicas" ]; then
  python3 -m venv heuristicas
fi

# Activar
# shellcheck disable=SC1091
source heuristicas/bin/activate

# Actualiza pip e instala dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt

# Registra el kernel de Jupyter con el nombre "Python (heuristicas)"
python -m ipykernel install --user --name heuristicas --display-name "Python (heuristicas)"

echo "Listo ✅
- Venv activado: heuristicas
- Dependencias instaladas desde requirements.txt
- Kernel registrado: Python (heuristicas)

Para activar manualmente más tarde:
  source heuristicas/bin/activate
"
