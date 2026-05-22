#!/usr/bin/env bash
# Generate gRPC Python stubs from .proto files
# Run from project root: bash scripts/gen_protos.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PROTO_DIR="$PROJECT_ROOT/protos"
OUT_DIR="$PROJECT_ROOT/app/grpc"
PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
        PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    fi
fi

cd "$PROJECT_ROOT"

echo "==> Generating gRPC stubs..."
echo "    protos : $PROTO_DIR"
echo "    output : $OUT_DIR"

mkdir -p "$OUT_DIR"

"$PYTHON_BIN" -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR"/*.proto

# Fix relative imports in generated files (grpc_tools generates broken imports)
echo "==> Fixing relative imports in generated stubs..."
for f in "$OUT_DIR"/*_pb2_grpc.py; do
    # Replace: from xxx_pb2 import  -->  from app.grpc.xxx_pb2 import
    sed -i 's/^import \([a-z_]*_pb2\) as /from app.grpc import \1 as /g' "$f"
done

# Ensure __init__.py exists
if [ ! -f "$OUT_DIR/__init__.py" ]; then
    cat > "$OUT_DIR/__init__.py" << 'INITEOF'
"""
Generated stubs and helpers for gRPC services.
To regenerate after modifying .proto files:

    bash scripts/gen_protos.sh
"""
INITEOF
fi

echo "==> Done! Generated files:"
ls -1 "$OUT_DIR"/*.py 2>/dev/null || echo "(none)"
