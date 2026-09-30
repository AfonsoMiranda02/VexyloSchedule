import sys
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.core.cache import cache
from django.core.cache.backends.db import DatabaseCache
from django.conf import settings
from website.models import BusinessInfo, BusinessOpeningHours, Service, StaffMember


class Command(BaseCommand):
    help = "Verifica se o ambiente de produção está completamente pronto, distinguindo infraestrutura técnica e configuração de negócio."

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
        parser.add_argument(
            '--require-business-ready',
            action='store_true',
            help='Exige que as configurações funcionais de negócio (empresa, horários, serviços ativos e profissionais) estejam completas.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> A verificar integridade e prontidão de produção do VexyloSchedule..."))
        has_error = False
        business_incomplete = False

        self.stdout.write("\n[1/2] Verificação da Infraestrutura Técnica:")

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
            from django.core.cache import caches
            default_cache = caches['default']
            backend_class = default_cache.__class__.__module__ + '.' + default_cache.__class__.__name__
            self.stdout.write(f"  [*] Backend de Cache ativo: {backend_class}")
            is_db_cache = isinstance(default_cache, DatabaseCache) or 'DatabaseCache' in backend_class

            if options.get('require_db_cache'):
                if not is_db_cache:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] Backend de Cache esperado: DatabaseCache. Ativo: {backend_class}"))
                    has_error = True
                else:
                    self.stdout.write(self.style.SUCCESS("  [OK] Backend de Cache DatabaseCache confirmado."))

            if is_db_cache or options.get('require_db_cache'):
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

        # 3. URLs Canónicas / APP_BASE_URL
        app_url = getattr(settings, 'APP_BASE_URL', None)
        if app_url:
            parsed = urlparse(app_url)
            if not settings.DEBUG and parsed.scheme != 'https':
                self.stdout.write(self.style.ERROR(f"  [ERRO] APP_BASE_URL ('{app_url}') deve utilizar HTTPS em produção."))
                has_error = True
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] APP_BASE_URL Canónico: {app_url}"))
        else:
            if not settings.DEBUG:
                self.stdout.write(self.style.ERROR("  [ERRO] APP_BASE_URL não definido em produção."))
                has_error = True
            else:
                self.stdout.write(self.style.WARNING("  [AVISO] APP_BASE_URL não definido (permitido em DEBUG=True)."))

        # 4. Email e SMTP
        if getattr(settings, 'EMAIL_CONFIGURED', False):
            host = getattr(settings, 'EMAIL_HOST', 'N/A')
            self.stdout.write(self.style.SUCCESS(f"  [OK] Email transacional (SMTP): Ativo (Host: {host})"))
        else:
            backend = getattr(settings, 'EMAIL_BACKEND', '')
            if 'console' in backend.lower() or 'locmem' in backend.lower():
                self.stdout.write(self.style.WARNING("  [INFO] Email transacional: Em modo consola/desenvolvimento."))
            elif 'dummy' in backend.lower():
                self.stdout.write(self.style.WARNING("  [AVISO] Email transacional desativado em produção via DISABLE_EMAIL_IN_PROD=true."))
            elif not settings.DEBUG:
                self.stdout.write(self.style.ERROR("  [ERRO] Email transacional não configurado em produção. O envio de recuperação de password não funcionará."))
                has_error = True
            else:
                self.stdout.write(self.style.WARNING("  [INFO] Email transacional: Em modo consola/desenvolvimento."))

        # 5. Google OAuth
        if getattr(settings, 'GOOGLE_OAUTH_ENABLED', False):
            self.stdout.write(self.style.SUCCESS("  [OK] Google OAuth 2.0: Ativo."))
        else:
            self.stdout.write(self.style.NOTICE("  [INFO] Google OAuth 2.0: Desativado (credenciais não fornecidas - modo opcional)."))

        self.stdout.write("\n[2/2] Verificação da Configuração de Negócio:")

        # 6. BusinessInfo e Horários
        require_biz = options.get('require_business_ready', False)
        try:
            info = BusinessInfo.objects.first()
            if not info:
                msg = "BusinessInfo não configurado na base de dados."
                if require_biz:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] {msg}"))
                    has_error = True
                else:
                    self.stdout.write(self.style.WARNING(f"  [AVISO] {msg}"))
                    business_incomplete = True
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Empresa configurada: '{info.name}' (Tel: {info.phone or 'Não definido'})"))

            hours_count = BusinessOpeningHours.objects.count()
            if hours_count < 7:
                msg = f"Existem apenas {hours_count}/7 dias de funcionamento configurados."
                if require_biz:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] {msg}"))
                    has_error = True
                else:
                    self.stdout.write(self.style.WARNING(f"  [AVISO] {msg}"))
                    business_incomplete = True
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Horários de funcionamento: 7 dias configurados."))

            active_services = Service.objects.filter(is_active=True).count()
            if active_services == 0:
                msg = "Não existem serviços ativos configurados para agendamento."
                if require_biz:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] {msg}"))
                    has_error = True
                else:
                    self.stdout.write(self.style.WARNING(f"  [AVISO] {msg}"))
                    business_incomplete = True
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Serviços ativos: {active_services} disponível(eis)."))

            active_staff = StaffMember.objects.filter(is_active=True).count()
            if active_staff == 0:
                msg = "Não existem profissionais ativos configurados para marcações."
                if require_biz:
                    self.stdout.write(self.style.ERROR(f"  [ERRO] {msg}"))
                    has_error = True
                else:
                    self.stdout.write(self.style.WARNING(f"  [AVISO] {msg}"))
                    business_incomplete = True
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Profissionais ativos: {active_staff} disponível(eis)."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [ERRO] Falha ao verificar dados de negócio: {e}"))
            has_error = True

        if has_error:
            raise CommandError("Verificação de prontidão de produção falhou com erros impeditivos.")

        if business_incomplete:
            self.stdout.write(self.style.WARNING(
                "\n==> Infraestrutura técnica validada com sucesso; configuração funcional do negócio ainda incompleta "
                "(complete os dados no painel de administração ou variáveis de negócio antes da abertura ao público)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n==> Todos os requisitos de produção (infraestrutura técnica e configuração funcional do negócio) foram validados com sucesso!"
            ))
