#!/bin/bash
# entrypoint.sh - Fluxo seguro de arranque (Produção/Render)

# Garante que em caso de erro, o script pára imediatamente
set -e

echo "A aplicar migrações na Base de Dados (Neon PostgreSQL)..."
python manage.py migrate --noinput

echo "A compilar os ficheiros estáticos (Whitenoise)..."
python manage.py collectstatic --noinput

echo "A iniciar o Gunicorn..."
# O binding para a variável de ambiente $PORT é essencial no Render
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3
