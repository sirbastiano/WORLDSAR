#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
PHIDOWN_DATA_DIR="${PHIDOWN_DATA_DIR:-${PROJECT_DIR}/phidown_data}"
PHIDOWN_CFG="${PHIDOWN_CFG:-${SCRIPT_DIR}/.s5cfg}"
S5CMD_NUM_WORKERS="${S5CMD_NUM_WORKERS:-1}"

source "${PROJECT_DIR}/.venv/bin/activate"

mkdir -p "${PHIDOWN_DATA_DIR}"
PRODUCT="${PRODUCT:-${1:?Usage: $0 <product_name>}}"

S5CMD_BIN="$(command -v s5cmd || true)"
if [[ -z "${S5CMD_BIN}" ]]; then
  echo "ERROR: s5cmd not found in PATH" >&2
  exit 127
fi

S5CMD_WRAP_DIR="$(mktemp -d)"
trap 'rm -rf "${S5CMD_WRAP_DIR}"' EXIT
cat > "${S5CMD_WRAP_DIR}/s5cmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec "${REAL_S5CMD}" --numworkers "${S5CMD_NUM_WORKERS}" "$@"
EOF
chmod +x "${S5CMD_WRAP_DIR}/s5cmd"

echo "phidown download: python -m phidown --name \"${PRODUCT}\" -o \"${PHIDOWN_DATA_DIR}/\" -c \"${PHIDOWN_CFG}\" --no-progress (s5cmd --numworkers ${S5CMD_NUM_WORKERS}) --mode safe"
REAL_S5CMD="${S5CMD_BIN}" S5CMD_NUM_WORKERS="${S5CMD_NUM_WORKERS}" PATH="${S5CMD_WRAP_DIR}:${PATH}" \
  python -m phidown --name "${PRODUCT}" -o "${PHIDOWN_DATA_DIR}/" -c "${PHIDOWN_CFG}" 
