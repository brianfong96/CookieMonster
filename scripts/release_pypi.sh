#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade build twine
python3 -m build
python3 -m twine check dist/*

echo "Built and validated distributions in dist/."
echo "Publish with: python3 -m twine upload dist/*"
