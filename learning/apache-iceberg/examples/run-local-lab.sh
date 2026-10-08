#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LAB_ENV=${ICEBERG_LAB_ENV:-/tmp/netai-iceberg-lab-venv}
WAREHOUSE=${ICEBERG_WAREHOUSE:-/tmp/netai-iceberg-lab/warehouse}

command -v java >/dev/null || {
  echo "오류: Java 17 또는 21이 필요합니다." >&2
  exit 1
}
command -v uv >/dev/null || {
  echo "오류: uv가 필요합니다. https://docs.astral.sh/uv/ 에서 설치 방법을 확인하세요." >&2
  exit 1
}

if [[ ! -x "$LAB_ENV/bin/python" ]]; then
  uv venv --python 3.12 "$LAB_ENV"
fi

uv pip install --python "$LAB_ENV/bin/python" "pyspark==4.0.4"
exec "$LAB_ENV/bin/python" "$SCRIPT_DIR/iceberg_local_lab.py" --warehouse "$WAREHOUSE" "$@"
