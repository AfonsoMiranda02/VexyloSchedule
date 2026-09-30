import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember


class Command(BaseCommand):
    help = 'Injeta os dados base caso a base de dados esteja vazia, de forma idempotente e segura por componente.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-demo',
            action='store_true',
            help='Injeta catálogo de serviços e profissionais de demonstração (permitido apenas em DEBUG=True ou com esta flag explícita).'
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("A iniciar verificação e inicialização de dados base...")

        # 1. Criar Superuser (Apenas se explicitamente solicitado via variáveis de ambiente seguras)
        create_su = os.getenv('CREATE_INITIAL_SUPERUSER', 'false').lower() in ('true', '1', 't')
        if create_su:
            su_user = os.getenv('INITIAL_SUPERUSER_USERNAME')
            su_email = os.getenv('INITIAL_SUPERUSER_EMAIL', 'admin@vexyloschedule.com')
            su_pass = os.getenv('INITIAL_SUPERUSER_PASSWORD')
            
            if su_user and su_pass:
                try:
                    validate_password(su_pass)
                    if su_pass.lower() == 'admin':
                        raise ValidationError("A palavra-passe 'admin' não é permitida.")
                    
                    if not User.objects.filter(username=su_user).exists():
                        User.objects.create_superuser(su_user, su_email, su_pass)
                        self.stdout.write(self.style.SUCCESS(f'Superuser "{su_user}" criado com sucesso.'))
                    else:
                        self.stdout.write(f'Superuser "{su_user}" já existe.')
                except ValidationError as e:
                    msg = f"ERRO: A password fornecida em INITIAL_SUPERUSER_PASSWORD não cumpre os requisitos: {e.messages}"
                    self.stdout.write(self.style.ERROR(msg))
                    raise CommandError(msg)
            else:
                self.stdout.write(self.style.WARNING(
                    'AVISO: CREATE_INITIAL_SUPERUSER=true foi configurado, mas as variáveis '
                    'INITIAL_SUPERUSER_USERNAME ou INITIAL_SUPERUSER_PASSWORD não foram fornecidas.'
                ))
        else:
            self.stdout.write('Criação de superuser omitida (defina CREATE_INITIAL_SUPERUSER=true se necessário).')

        with transaction.atomic():
            # 2. Business Info
            business = BusinessInfo.objects.first()
            if not business:
                if settings.DEBUG or kwargs.get('with_demo'):
                    business = BusinessInfo.objects.create(
                        name="Salão & Barbearia Demo",
                        address="Avenida Central, 100",
                        phone="912345678",
                        whatsapp="912345678",
                        email="contacto@barbeariademo.pt",
                        schedule="Segunda a Sábado (Quarta e Domingo encerrado): 09:00 - 19:00",
                        description="Solução de marcações online moderna e rápida."
                    )
                    self.stdout.write(self.style.SUCCESS(f'BusinessInfo criada: "{business.name}".'))
                else:
                    # Em produção (DEBUG=False): Nunca inventar moradas ou números falsos
                    init_name = os.getenv('INITIAL_BUSINESS_NAME')
                    if init_name:
                        business = BusinessInfo.objects.create(
                            name=init_name,
                            address=os.getenv('INITIAL_BUSINESS_ADDRESS', ''),
                            phone=os.getenv('INITIAL_BUSINESS_PHONE', ''),
                            whatsapp=os.getenv('INITIAL_BUSINESS_WHATSAPP', os.getenv('INITIAL_BUSINESS_PHONE', '')),
                            email=os.getenv('INITIAL_BUSINESS_EMAIL', ''),
                            schedule=os.getenv('INITIAL_BUSINESS_SCHEDULE', 'Segunda a Sábado: 09:00 - 19:00'),
                            description=os.getenv('INITIAL_BUSINESS_DESCRIPTION', '')
                        )
                        self.stdout.write(self.style.SUCCESS(f'BusinessInfo configurada via variáveis de ambiente: "{business.name}".'))
                    else:
                        self.stdout.write(self.style.NOTICE(
                            'BusinessInfo não configurada. Em produção, os dados reais do estabelecimento devem '
                            'ser introduzidos no Painel de Administração ou via INITIAL_BUSINESS_*.'
                        ))
            else:
                self.stdout.write(f'BusinessInfo já configurada: "{business.name}".')

            # 3. Horários Estruturados (7 dias garantidos se a empresa existir)
            if business:
                created_hours = 0
                for w in range(7):
                    is_open = (w not in (2, 6))
                    _, created = BusinessOpeningHours.objects.get_or_create(
                        business=business,
                        weekday=w,
                        defaults={
                            'is_open': is_open,
                            'opening_time': "09:00:00",
                            'closing_time': "19:00:00",
                            'lunch_start': "13:00:00",
                            'lunch_end': "14:00:00"
                        }
                    )
                    if created:
                        created_hours += 1

                if created_hours > 0:
                    self.stdout.write(self.style.SUCCESS(f'{created_hours} dias de funcionamento criados para a empresa.'))
                else:
                    self.stdout.write('Horários de funcionamento já se encontram completos (7 dias).')

            # 4. Categorias e Serviços
            if settings.DEBUG or kwargs.get('with_demo'):
                if not ServiceCategory.objects.exists() and not Service.objects.exists():
                    cat_cabelo = ServiceCategory.objects.create(name="Cabelo", order=1)
                    cat_barba = ServiceCategory.objects.create(name="Barba", order=2)
                    cat_combos = ServiceCategory.objects.create(name="Combos", order=3)

                    Service.objects.create(category=cat_cabelo, name="Corte Tradicional", price=15.00, duration=30, is_active=True)
                    Service.objects.create(category=cat_cabelo, name="Corte Degradê / Fade", price=18.00, duration=45, is_active=True)
                    Service.objects.create(category=cat_barba, name="Barba Completa com Toalha Quente", price=12.00, duration=30, is_active=True)
                    Service.objects.create(category=cat_combos, name="Cabelo + Barba VIP", price=25.00, duration=60, is_active=True)
                    self.stdout.write(self.style.SUCCESS('Categorias e serviços de demonstração criados.'))
                else:
                    self.stdout.write('Catálogo de serviços já contém dados existentes.')

                # 5. Profissionais
                if not StaffMember.objects.exists():
                    StaffMember.objects.create(name="Alexandre Silva", role="Master Barber", is_active=True)
                    StaffMember.objects.create(name="Diogo Costa", role="Especialista em Fade", is_active=True)
                    self.stdout.write(self.style.SUCCESS('Profissionais de demonstração criados.'))
                else:
                    self.stdout.write('Membros da equipa já existentes.')
            else:
                self.stdout.write('Em produção, o catálogo de serviços e profissionais não é inventado automaticamente (omitidos para segurança).')

        self.stdout.write(self.style.SUCCESS('Dados base verificados/inicializados com sucesso.'))
