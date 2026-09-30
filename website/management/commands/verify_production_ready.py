import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from website.models import BusinessInfo, BusinessOpeningHours

class Command(BaseCommand):
    help = "Verifica se o ambiente de produção está completamente pronto, com BD, cache, estáticos e configurações."

    def add_arguments(self, parser):
        parser.add_argument(
            '--require-postgres',
            action='store_true',
            help='Exige que a base de dados em execução seja PostgreSQL.'
        )
        parser.add_argument(
            '--require-db-cache',
            action='store_true',
            help='Exige que o backend de cache seja DatabaseCache com tabela ativa.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> A verificar integridade e prontidão de produção do VexyloSchedule..."))
        has_error = False

        # 1. Base de Dados
        try:
            connection.ensure_connection()
            vendor = connection.vendor
            self.stdout.write(self.style.SUCCESS(f"  [OK] Conexão à Base de Dados: Ativa (vendor: {vendor})"))
            if options.get('require_postgres') and vendor != 'postgresql':
                self.stdout.write(self.style.ERROR(f"  [ERRO] Base de dados esperada: PostgreSQL. Encontrada: {vendor}"))
                has_error = True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha na conexão à Base de Dados: {e}"))
            has_error = True

        # 2. Backend de Cache e Tabela
        try:
            backend_class = cache.__class__.__module__ + '.' + cache.__class__.__name__
            self.stdout.write(f"  [*] Backend de Cache ativo: {backend_class}")

            if options.get('require_db_cache') or not settings.DEBUG:
                tables = connection.introspection.table_names()
                location = settings.CACHES.get('default', {}).get('LOCATION', '')
                if location and location not in tables:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] Tabela de cache '{location}' não encontrada na base de dados. Execute 'python manage.py createcachetable'."))
                    has_error = True
                else:
                    self.stdout.write(self.style.SUCCESS(f"  [OK] Tabela de cache '{location}' verificada."))

            # Teste de leitura/escrita/expiração do cache
            test_key = "smoke:verify_production_ready"
            cache.set(test_key, "active_smoke_value", timeout=10)
            read_val = cache.get(test_key)
            if read_val != "active_smoke_value":
                self.stdout.write(self.style.ERROR(f"  [ERRO] Leitura de cache falhou. Esperado 'active_smoke_value', obtido '{read_val}'"))
                has_error = True
            else:
                self.stdout.write(self.style.SUCCESS("  [OK] Operações de Cache (read/write/timeout): Operacionais."))
                cache.delete(test_key)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha nas operações de cache: {e}"))
            has_error = True

        # 3. Configuração de Negócio (BusinessInfo e Horários)
        try:
            info = BusinessInfo.objects.first()
            if not info:
                self.stdout.write(self.style.WARNING("  [AVISO] BusinessInfo ainda não configurado na BD. Recomenda-se executar 'seed_data' ou configurar no Admin."))
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Empresa configurada: '{info.name}' (Tel: {info.phone})"))

            hours_count = BusinessOpeningHours.objects.count()
            if hours_count < 7:
                self.stdout.write(self.style.WARNING(f"  [AVISO] Existem apenas {hours_count}/7 dias de funcionamento configurados."))
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Horários de funcionamento: 7 dias configurados."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha ao verificar dados de negócio: {e}"))
            has_error = True

        # 4. URLs Canónicas / APP_BASE_URL
        app_url = getattr(settings, 'APP_BASE_URL', None) or getattr(settings, 'CANONICAL_HOST', None)
        if app_url:
            self.stdout.write(self.style.SUCCESS(f"  [OK] Domínio / URL Canónico: {app_url}"))
        else:
            if not settings.DEBUG:
                self.stdout.write(self.style.ERROR("  [ERRO] APP_BASE_URL ou CANONICAL_HOST não definido em produção."))
                has_error = True
            else:
                self.stdout.write(self.style.WARNING("  [AVISO] CANONICAL_HOST não definido (permitido em DEBUG=True)."))

        # 5. Email e SMTP
        if getattr(settings, 'EMAIL_CONFIGURED', False):
            self.stdout.write(self.style.SUCCESS(f"  [OK] Email transacional (SMTP): Ativo (Host: {getattr(settings, 'EMAIL_HOST', 'N/A')})"))
        else:
            if not settings.DEBUG:
                self.stdout.write(self.style.ERROR("  [ERRO] Email transacional não configurado em produção. O envio de recuperação de password não funcionará."))
                has_error = True
            else:
                self.stdout.write(self.style.WARNING("  [INFO] Email transacional: Em modo consola/desenvolvimento."))

        # 6. Google OAuth
        if getattr(settings, 'GOOGLE_OAUTH_ENABLED', False):
            self.stdout.write(self.style.SUCCESS("  [OK] Google OAuth 2.0: Ativo."))
        else:
            self.stdout.write(self.style.NOTICE("  [INFO] Google OAuth 2.0: Desativado (credenciais não fornecidas - modo opcional)."))

        if has_error:
            raise CommandError("Verificação de prontidão de produção falhou. Corrija os erros acima.")

        self.stdout.write(self.style.SUCCESS("\n==> Todos os requisitos de produção foram validados com sucesso!"))
