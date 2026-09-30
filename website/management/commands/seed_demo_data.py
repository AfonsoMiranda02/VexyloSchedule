from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from decimal import Decimal
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember


class Command(BaseCommand):
    help = 'Injeta dados de demonstração (catálogo de serviços, profissionais e empresa demo) para desenvolvimento e testes.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write(self.style.WARNING(
                "ATENÇÃO: A injetar dados de demonstração com DEBUG=False. "
                "Certifique-se de que este ambiente não é o de produção pública real."
            ))

        with transaction.atomic():
            # 1. Business Info Demo
            business = BusinessInfo.objects.first()
            if not business:
                business = BusinessInfo.objects.create(
                    name="Salão & Barbearia Demo",
                    address="Avenida Central, 100, Lisboa",
                    phone="912345678",
                    whatsapp="912345678",
                    email="contacto@barbeariademo.pt",
                    schedule="Segunda a Sábado (Quarta e Domingo encerrado): 09:00 - 19:00",
                    description="Espaço de demonstração do sistema VexyloSchedule."
                )
                self.stdout.write(self.style.SUCCESS(f'Empresa de demonstração criada: "{business.name}".'))
            else:
                self.stdout.write(f'Empresa existente: "{business.name}".')

            # 2. Horários de Funcionamento (7 dias)
            for w in range(7):
                BusinessOpeningHours.objects.get_or_create(
                    business=business,
                    weekday=w,
                    defaults={
                        'is_open': (w not in (2, 6)),
                        'opening_time': "09:00:00",
                        'closing_time': "19:00:00",
                        'lunch_start': "13:00:00",
                        'lunch_end': "14:00:00"
                    }
                )

            # 3. Categorias e Serviços Demo
            if not ServiceCategory.objects.exists() and not Service.objects.exists():
                cat_cabelo = ServiceCategory.objects.create(name="Cabelo", order=1)
                cat_barba = ServiceCategory.objects.create(name="Barba", order=2)
                cat_combos = ServiceCategory.objects.create(name="Combos", order=3)

                Service.objects.create(category=cat_cabelo, name="Corte Tradicional", price=Decimal('15.00'), duration=30, is_active=True)
                Service.objects.create(category=cat_cabelo, name="Corte Degradê / Fade", price=Decimal('18.00'), duration=45, is_active=True)
                Service.objects.create(category=cat_barba, name="Barba Completa com Toalha Quente", price=Decimal('12.00'), duration=30, is_active=True)
                Service.objects.create(category=cat_combos, name="Cabelo + Barba VIP", price=Decimal('25.00'), duration=60, is_active=True)
                self.stdout.write(self.style.SUCCESS('Categorias e serviços de demonstração criados.'))
            else:
                self.stdout.write('Catálogo de serviços já contém dados.')

            # 4. Profissionais Demo
            if not StaffMember.objects.exists():
                StaffMember.objects.create(name="Alexandre Silva", role="Master Barber", is_active=True)
                StaffMember.objects.create(name="Diogo Costa", role="Especialista em Fade", is_active=True)
                self.stdout.write(self.style.SUCCESS('Profissionais de demonstração criados.'))
            else:
                self.stdout.write('Membros da equipa já existentes.')

        self.stdout.write(self.style.SUCCESS('Dados de demonstração injetados com sucesso.'))
