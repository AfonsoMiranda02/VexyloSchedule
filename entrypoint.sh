#!/usr/bin/env bash
# entrypoint.sh - Fluxo seguro e determinístico de arranque (Produção/Render/Docker)
set -euo pipefail

echo "==> A aplicar migrações na Base de Dados..."
python manage.py migrate --noinput

echo "==> A compilar ficheiros estáticos (Whitenoise)..."
python manage.py collectstatic --noinput

echo "==> A verificar dados base do sistema..."
python manage.py seed_data

echo "==> A iniciar servidor de aplicação Gunicorn..."
exec gunicorn core.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 3 --timeout 60
