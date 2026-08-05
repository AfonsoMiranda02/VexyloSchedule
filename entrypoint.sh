#!/bin/bash
# Stop on error
set -e

echo "=== A limpar Base de Dados antiga (Clean State) ==="
rm -f db.sqlite3

echo "=== A recolher ficheiros estáticos (WhiteNoise) ==="
python manage.py collectstatic --noinput

echo "=== A gerar migrações ==="
python manage.py makemigrations website
python manage.py makemigrations

echo "=== A aplicar migrações na Base de Dados ==="
python manage.py migrate --noinput

echo "=== A verificar SuperUser ==="
python -c "
import os, django
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.getenv('SUPERUSER_USERNAME', 'admin')
password = os.getenv('SUPERUSER_PASSWORD')
if password:
    user, created = User.objects.get_or_create(username=username, defaults={'email': 'contact@nexoraschedule.com'})
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.save()
    if created:
        print('✅ SuperUser criado com sucesso com a password de SUPERUSER_PASSWORD.')
    else:
        print('✅ SuperUser existente atualizado com a password de SUPERUSER_PASSWORD.')
else:
    print('⚠️ SUPERUSER_PASSWORD não encontrada no ambiente (.env). Nenhum SuperUser foi criado ou modificado em texto limpo.')
"

echo "=== A injetar dados de teste (Seed Data) ==="
python manage.py seed_data

echo "=== A iniciar o servidor Django ==="
exec python manage.py runserver 0.0.0.0:${PORT:-10000}
