from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Testimonial

class Command(BaseCommand):
    help = 'Injeta os dados iniciais caso a base de dados esteja completamente vazia'

    def handle(self, *args, **kwargs):
        # 1. Verifica se a BD já tem dados (se já tem superuser, não fazemos nada)
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('A base de dados já contém um superuser. O seeder foi ignorado para não sobrepor dados.'))
            return

        self.stdout.write("A iniciar injeção de dados iniciais automatizados...")

        # 2. Criar Superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@vexyloschedule.com', 'admin')
            self.stdout.write(self.style.SUCCESS('Superuser "admin" criado com sucesso (password: admin)!'))

        # 3. Business Info
        if not BusinessInfo.objects.exists():
            BusinessInfo.objects.create(
                name="Barbearia Default",
                address="Rua Principal, 123",
                phone="912345678",
                whatsapp="912345678",
                email="contact@barbearia.com",
                schedule="Segunda a Sábado: 09:00 - 19:00",
                description="A tua nova solução de marcações online."
            )
            self.stdout.write(self.style.SUCCESS('BusinessInfo default criado!'))

        # 4. Categorias e Serviços
        if not ServiceCategory.objects.exists():
            cat = ServiceCategory.objects.create(name="Cortes de Cabelo", order=1)
            Service.objects.create(name="Corte de Cabelo (Homem)", category=cat, price=15.00, duration=30)
            Service.objects.create(name="Corte de Barba", category=cat, price=10.00, duration=30)
            Service.objects.create(name="Cabelo + Barba", category=cat, price=20.00, duration=60)
            self.stdout.write(self.style.SUCCESS('Serviços default criados!'))

        # 5. Membros da Equipa
        if not StaffMember.objects.exists():
            StaffMember.objects.create(name="João (Barbeiro)", role="Barbeiro Principal")
            self.stdout.write(self.style.SUCCESS('Staff default criado!'))

        self.stdout.write(self.style.SUCCESS('✨ Instalação concluída! O sistema está pronto a ser entregue ao cliente.'))
