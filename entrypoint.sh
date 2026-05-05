#!/bin/bash
# Stop on error
set -e

echo "=== A recolher ficheiros estáticos (WhiteNoise) ==="
python manage.py collectstatic --noinput

echo "=== A aplicar migrações na Base de Dados ==="
# Em produção não se faz makemigrations, apenas migrate
python manage.py migrate --noinput

echo "=== A verificar SuperUser ==="
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@agencia.com', 'admin')
    print('✅ SuperUser admin criado com sucesso.')
else:
    print('ℹ️ SuperUser admin já existe.')
"

echo "=== A injetar dados de teste (Seed Data) ==="
python manage.py seed_data

echo "=== A iniciar o servidor Django ==="
# O Render usa a porta 10000 por defeito, ou a variável $PORT
exec python manage.py runserver 0.0.0.0:${PORT:-10000}