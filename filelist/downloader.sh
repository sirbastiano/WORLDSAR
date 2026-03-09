#!/usr/bin/env bash
set -euo pipefail

# Config
ENV_NAME="phidown"
OUT_DIR="/lustre/projects/1001/rdelprete/WORLDSAR/phidown_data/SR"
CFG="/lustre/projects/1001/rdelprete/service/.s5cfg"
LIST_FILE="${1:-products_to_redownload.txt}"          # podes pasar otro archivo por argumento
JOBS="${JOBS:-1}"                       # export JOBS=4 para paralelizar
LOG_DIR="${LOG_DIR:-./logs_phidown}"

mkdir -p "$OUT_DIR" "$LOG_DIR"

# Activar conda de forma robusta en batch
# Si ya tenes `conda` funcional, esto suele ser suficiente:
source /lustre/projects/1001/miniconda3/bin/activate "$ENV_NAME"

if ! command -v phidown >/dev/null 2>&1; then
  echo "ERROR: phidown no esta en PATH. Revisar el entorno conda: $ENV_NAME" >&2
  exit 1
fi

if [[ ! -f "$LIST_FILE" ]]; then
  echo "ERROR: no existe LIST_FILE: $LIST_FILE" >&2
  exit 1
fi

# Limpia lineas vacias y comentarios
mapfile -t PRODUCTS < <(grep -vE '^\s*($|#)' "$LIST_FILE" | sed 's/^\s\+//; s/\s\+$//')

if [[ "${#PRODUCTS[@]}" -eq 0 ]]; then
  echo "ERROR: lista vacia en $LIST_FILE" >&2
  exit 1
fi

download_one() {
  local product="$1"
  local safe_dir="${OUT_DIR}/${product}"
  local log="${LOG_DIR}/${product}.log"

  # Idempotencia: si ya existe, saltar
  if [[ -d "$safe_dir" ]]; then
    echo "[SKIP] ya existe: $safe_dir"
    return 0
  fi

  echo "[DOWN] $product"
  # Log por producto
  {
    echo "=== $(date -Is) START $product ==="
    phidown --name "$product" -o "$OUT_DIR" -c "$CFG"
    echo "=== $(date -Is) END   $product ==="
  } >"$log" 2>&1

  # Verificacion minima
  if [[ ! -d "$safe_dir" ]]; then
    echo "ERROR: descarga fallo o incompleta. No existe: $safe_dir (ver $log)" >&2
    return 2
  fi
}

export -f download_one
export OUT_DIR CFG LOG_DIR

# Secuencial o paralelo
if [[ "$JOBS" -le 1 ]]; then
  for p in "${PRODUCTS[@]}"; do
    download_one "$p"
  done
else
  # xargs paralelo (normalmente disponible)
  printf "%s\n" "${PRODUCTS[@]}" | xargs -I{} -P "$JOBS" bash -lc 'download_one "$@"' _ {}
fi

echo "Listo. Logs en: $LOG_DIR"