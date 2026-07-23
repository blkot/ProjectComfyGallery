#!/bin/sh
set -eu

alembic -c packages/py/core/alembic.ini upgrade head
python -m comfy_gallery_core.cli create-admin --if-missing
exec uvicorn comfy_gallery_api.main:app --host 0.0.0.0 --port 8000
