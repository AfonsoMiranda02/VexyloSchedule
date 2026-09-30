import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember


class Command(BaseCommand):
    help = 'Injeta os dados base caso a base de dados esteja vazia, de forma idempotente e segura.'

    def handle(self, *args, **kwargs):
        # 1. Verifica se a BD já tem dados
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('A base de dados já contém um superuser. O seeder foi ignorado para não sobrepor dados.'))
            return

        self.stdout.write("A iniciar verificação e inicialização de dados base...")

        # 2. Criar Superuser (Apenas se explicitamente solicitado via variáveis de ambiente seguras)
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
                    self.stdout.write(self.style.ERROR(
                        f'ERRO: A password fornecida em INITIAL_SUPERUSER_PASSWORD não cumpre os requisitos de segurança: {e.messages}'
                    ))
            else:
                self.stdout.write(self.style.WARNING(
                    'AVISO: CREATE_INITIAL_SUPERUSER=true foi configurado, mas as variáveis '
                    'INITIAL_SUPERUSER_USERNAME ou INITIAL_SUPERUSER_PASSWORD não foram fornecidas. Nenhum superuser foi criado.'
                ))
        else:
            self.stdout.write('Criação de superuser omitida (defina CREATE_INITIAL_SUPERUSER=true com credenciais fortes se necessário).')

        with transaction.atomic():
            # 3. Business Info e Horários Estruturados
            if not BusinessInfo.objects.exists():
                business = BusinessInfo.objects.create(
                    name=os.getenv('DEFAULT_BUSINESS_NAME', 'VexyloSchedule Salão Demo'),
                    address=os.getenv('DEFAULT_BUSINESS_ADDRESS', 'Avenida Central, 100'),
                    phone=os.getenv('DEFAULT_BUSINESS_PHONE', '910000000'),
                    whatsapp=os.getenv('DEFAULT_BUSINESS_WHATSAPP', '910000000'),
                    email=os.getenv('DEFAULT_BUSINESS_EMAIL', 'contacto@vexyloschedule.com'),
                    schedule="Segunda a Sábado (Quarta e Domingo encerrado): 09:00 - 19:00",
                    description="Solução de marcações online moderna e rápida."
                )
                
                # Criar os 7 dias da semana (Quarta-feira=2 e Domingo=6 encerrados por omissão)
                for w in range(7):
                    is_open = (w not in (2, 6))
                    BusinessOpeningHours.objects.create(
                        business=business,
                        weekday=w,
                        is_open=is_open,
                        opening_time='09:00:00',
                        closing_time='19:00:00',
                        lunch_start=None,
                        lunch_end=None
                    )
                self.stdout.write(self.style.SUCCESS('BusinessInfo e horários semanais estruturados criados.'))

            # 4. Categorias e Serviços
            if not ServiceCategory.objects.exists():
                cat = ServiceCategory.objects.create(name="Cabelo & Barba", order=1)
                Service.objects.create(name="Corte de Cabelo", category=cat, price=15.00, duration=30)
                Service.objects.create(name="Corte de Barba", category=cat, price=10.00, duration=30)
                Service.objects.create(name="Cabelo + Barba Completo", category=cat, price=22.00, duration=60)
                self.stdout.write(self.style.SUCCESS('Serviços base criados.'))

            # 5. Membros da Equipa
            if not StaffMember.objects.exists():
                StaffMember.objects.create(name="Profissional Principal", role="Especialista Sénior")
                self.stdout.write(self.style.SUCCESS('Membro da equipa base criado.'))

        self.stdout.write(self.style.SUCCESS('Dados base verificados/inicializados com sucesso.'))
