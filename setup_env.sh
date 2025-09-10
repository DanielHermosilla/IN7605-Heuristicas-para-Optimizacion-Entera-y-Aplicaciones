#!/usr/bin/env bash
set -euo pipefail

# === Config ===
VENV_DIR=".venv"   # usa un nombre simple/ASCII
REQ_FILE="requirements.txt"

# === Detectar python3 ===
PYTHON_BIN="$(command -v python3 || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "❌ No se encontró python3 en PATH"; exit 1
fi
echo "ℹ️  Usando: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>/dev/null || echo '?'))"

# === Funciones auxiliares ===
have_venv_python() {
  [ -x "$VENV_DIR/bin/python" ]
}

print_tree() {
  echo "── Contenido de $VENV_DIR/bin:"
  ls -l "$VENV_DIR/bin" || true
}

safe_recreate_dir() {
  rm -rf "$VENV_DIR" 2>/dev/null || true
  mkdir -p "$VENV_DIR"
  rmdir "$VENV_DIR" 2>/dev/null || true  # vuelve a dejarlo “no creado”
}

# === 1) Intento normal de venv ===
if [ -d "$VENV_DIR" ] && ! have_venv_python; then
  echo "⚠️  Existe $VENV_DIR pero está corrupto (sin bin/python). Lo reharemos."
  rm -rf "$VENV_DIR"
fi

if ! have_venv_python; then
  echo "➡️  Creando venv (intento 1: venv estándar)…"
  "$PYTHON_BIN" -m venv "$VENV_DIR" || true
fi

# === 2) Reparar ensurepip y reintentar con --copies si faltan binarios ===
if ! have_venv_python; then
  echo "⚠️  No apareció $VENV_DIR/bin/python. Reparo pip/ensurepip y reintento…"
  "$PYTHON_BIN" -m ensurepip --upgrade || true
  safe_recreate_dir
  echo "➡️  Creando venv (intento 2: venv --copies)…"
  "$PYTHON_BIN" -m venv --copies "$VENV_DIR" || true
fi

# === 3) Plan B: virtualenv (sin flags no soportados) ===
if ! have_venv_python; then
  echo "⚠️  Seguimos sin $VENV_DIR/bin/python."
  echo "➡️  Plan B: virtualenv (usuario)."
  "$PYTHON_BIN" -m pip install --user --upgrade pip wheel setuptools virtualenv
  safe_recreate_dir
  "$PYTHON_BIN" -m virtualenv "$VENV_DIR"  # <- sin --upgrade-deps
fi

# === 4) Verificación final ===
if ! have_venv_python; then
  echo "❌ No se creó correctamente el venv (no existe $VENV_DIR/bin/python)."
  print_tree
  echo "
Sugerencias:
  • Mueve el proyecto a una ruta SIN acentos ni espacios, p.ej.:
      ~/proyectos/heuristicas
    y vuelve a ejecutar el script.
  • Reinstala Python de Homebrew:
      brew reinstall python
  • O usa Python de python.org (a veces arregla venv/ensurepip en macOS).
"
  exit 1
fi

print_tree

# === 5) Activar (opcional) ===
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" || true

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# === 6) pip & deps ===
"$VENV_PY" -m pip install --upgrade pip wheel setuptools
if [ -f "$REQ_FILE" ]; then
  "$VENV_PIP" install -r "$REQ_FILE"
else
  echo "⚠️  No hay $REQ_FILE; omito deps."
fi

# === 7) Registrar kernel de Jupyter ===
"$VENV_PY" -m ipykernel install --user --name "$(basename "$VENV_DIR")" \
  --display-name "Python ($(basename "$VENV_DIR"))"

echo "✅ Listo
- Venv: $VENV_DIR
- Python: $("$VENV_PY" --version)
- Kernel Jupyter: Python ($(basename "$VENV_DIR"))

Para activar:
  source $VENV_DIR/bin/activate
"
