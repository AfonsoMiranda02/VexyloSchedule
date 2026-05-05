from django.core.management.base import BaseCommand
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Testimonial

class Command(BaseCommand):
    help = 'Injeta os dados iniciais do Cabeleireiro'

    def handle(self, *args, **kwargs):
        self.stdout.write("A iniciar injeção de dados...")

        # 1. Business Info
        info, created = BusinessInfo.objects.get_or_create(
            name="Duo Space Cabeleireiro",
            defaults={
                'address': 'R. Henrique Lopes 170, 4900-716 Viana do Castelo',
                'phone': '966 579 620',
                'whatsapp': '351966579620',
                'schedule': 'Seg, Ter, Qui, Sex: 09:30 – 19:00\nSábado: 08:30 – 18:00\nQuarta e Domingo: Encerrado',
                'google_maps_url': 'https://maps.google.com/?q=R.+Henrique+Lopes+170,+Viana+do+Castelo'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('BusinessInfo criado com sucesso!'))

        # 2. Categorias
        cat_estetica, _ = ServiceCategory.objects.get_or_create(name="Estética Avançada", defaults={'order': 1})
        cat_epilacao, _ = ServiceCategory.objects.get_or_create(name="Epilação", defaults={'order': 2})

        # 3. Serviços Estética
        servicos_estetica = [
            ("Lipocavitação", 35.00),
            ("Limpeza de pele completa com ampola", 24.50),
        ]
        
        for nome, preco in servicos_estetica:
            Service.objects.get_or_create(name=nome, category=cat_estetica, defaults={'price': preco})

        # 4. Serviços Epilação
        servicos_epilacao = [
            ("Epilação de Perna completa + virilha + axila", 13.00),
            ("Epilação de Meia perna + virilha + axila", 11.00),
            ("Epilação de Axila + buço + sobrancelha", 6.00),
        ]

        for nome, preco in servicos_epilacao:
            Service.objects.get_or_create(name=nome, category=cat_epilacao, defaults={'price': preco})

        # 5. Membros da Equipa
        StaffMember.objects.get_or_create(name="Direção Duo Space", defaults={'role': 'Diretora e Especialista'})
        StaffMember.objects.get_or_create(name="Equipa Duo Space", defaults={'role': 'Esteticista'})
        
        # 6. Testemunhos Premium
        Testimonial.objects.get_or_create(
            client_name="Maria João",
            defaults={'text': 'Melhor depilação a laser de Viana do Castelo! O espaço é muito acolhedor. Recomendo a 100%!', 'rating': 5}
        )
        Testimonial.objects.get_or_create(
            client_name="Inês Castro",
            defaults={'text': 'Experimentei a massagem relaxante e foi incrível. Preços justos para um serviço super premium.', 'rating': 5}
        )
        Testimonial.objects.get_or_create(
            client_name="Carla Mendes",
            defaults={'text': 'Atendimento rápido e muito focado no cliente. Adoro a simpatia de toda a equipa.', 'rating': 4}
        )

        self.stdout.write(self.style.SUCCESS('Dados injetados com sucesso!'))
