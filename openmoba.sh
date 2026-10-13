#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Usa python3 do sistema se disponível, senão python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERRO] Python 3 não foi encontrado no sistema. Instale o Python 3 para executar o OpenMoba."
    exit 1
fi

"$PYTHON_CMD" main.py "$@"
