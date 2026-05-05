from django.core.management.base import BaseCommand
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Testimonial

class Command(BaseCommand):
    help = 'Injeta os dados iniciais do Cabeleireiro Teresa Pereira'

    def handle(self, *args, **kwargs):
        self.stdout.write("A iniciar injeção de dados para Teresa Pereira...")

        # 1. Business Info
        BusinessInfo.objects.all().delete()
        info = BusinessInfo.objects.create(
            name="Teresa Pereira Cabeleireiro e Estética",
            address="Praça Alto Minho Loja 109 - CC Torre Active Center, 4900-439 Viana do Castelo",
            phone="963474965",
            email="cabeleireirosteresapereira@hotmail.com",
            schedule="Segunda a Sábado das 09:00 às 19:00. Domingo: Encerrado.",
            google_maps_url="https://maps.google.com/?q=Praça+Alto+Minho+Loja+109,+Viana+do+Castelo",
            description="Um espaço renovado e acolhedor localizado a poucos minutos do centro da Cidade de Viana do Castelo, onde a Beleza e o bem-estar acontecem."
        )
        self.stdout.write(self.style.SUCCESS('BusinessInfo criado com sucesso!'))

        # 2. Categorias
        ServiceCategory.objects.all().delete()
        cat_cabelo = ServiceCategory.objects.create(name="Cabeleireiro", order=1)
        cat_estetica = ServiceCategory.objects.create(name="Estética e Bem-estar", order=2)
        cat_unhas = ServiceCategory.objects.create(name="Manicure e Pedicure", order=3)

        # 3. Serviços (Preço fixo 15.00€ para demo)
        Service.objects.all().delete()
        servicos = [
            # Cabeleireiro
            ("Tratamento Capilar", cat_cabelo),
            ("Próteses e Perucas (Alopecia/Oncologia)", cat_cabelo),
            # Estética
            ("Tratamentos Rosto e Corpo", cat_estetica),
            ("Maquilhagem", cat_estetica),
            ("Massagens", cat_estetica),
            ("Depilação", cat_estetica),
            # Unhas
            ("Manicure e Pedicure", cat_unhas),
            ("Unhas de Gel", cat_unhas),
        ]
        
        for nome, categoria in servicos:
            Service.objects.create(name=nome, category=categoria, price=15.00)

        # 4. Membros da Equipa
        StaffMember.objects.all().delete()
        StaffMember.objects.create(name="Teresa Pereira", role="Diretora e Especialista")
        StaffMember.objects.create(name="Equipa Teresa Pereira", role="Esteticista")
        
        # 5. Testemunhos
        Testimonial.objects.all().delete()
        Testimonial.objects.create(
            client_name="Ana Silva",
            text='Excelente atendimento e um espaço muito acolhedor. Recomendo os tratamentos de rosto!', 
            rating=5
        )
        Testimonial.objects.create(
            client_name="Ricardo Gomes",
            text='Profissionalismo de topo. A Teresa é fantástica.', 
            rating=5
        )

        self.stdout.write(self.style.SUCCESS('Dados da Teresa Pereira injetados com sucesso!'))
