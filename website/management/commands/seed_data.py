from django.core.management.base import BaseCommand
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Testimonial

class Command(BaseCommand):
    help = 'Injeta os dados iniciais genéricos do VexyloSchedule'

    def handle(self, *args, **kwargs):
        self.stdout.write("A iniciar injeção de dados genéricos para VexyloSchedule...")

        # 1. Business Info
        BusinessInfo.objects.all().delete()
        BusinessInfo.objects.create(
            name="VexyloSchedule",
            address="[MORADA COMPLETA]",
            phone="[TELEFONE]",
            email="contact@vexyloschedule.com",
            schedule="Segunda a Sexta: 09:00 - 18:00",
            google_maps_url="",
            description="Solução completa para gestão de agendamentos e serviços online."
        )
        self.stdout.write(self.style.SUCCESS('BusinessInfo criado com sucesso!'))

        # 2. Categorias
        ServiceCategory.objects.all().delete()
        cat_principal = ServiceCategory.objects.create(name="Serviços Gerais", order=1)

        # 3. Serviços
        Service.objects.all().delete()
        servicos = [
            ("Serviço Base 1", cat_principal, 10.00),
            ("Serviço Base 2", cat_principal, 20.00),
        ]
        
        for nome, categoria, preco in servicos:
            Service.objects.create(name=nome, category=categoria, price=preco)

        # 4. Membros da Equipa
        StaffMember.objects.all().delete()
        StaffMember.objects.create(name="Membro Equipa 1", role="Profissional")
        
        # 5. Testemunhos
        Testimonial.objects.all().delete()
        Testimonial.objects.create(
            client_name="Cliente Exemplo",
            text="Excelente serviço e facilidade de agendamento.", 
            rating=5
        )

        self.stdout.write(self.style.SUCCESS('Dados genéricos do VexyloSchedule injetados com sucesso!'))
