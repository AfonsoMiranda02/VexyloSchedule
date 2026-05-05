from django.core.management.base import BaseCommand
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Testimonial

class Command(BaseCommand):
    help = 'Injeta os dados iniciais do O Cabeleireiro - Oficina Orgânica'

    def handle(self, *args, **kwargs):
        self.stdout.write("A iniciar injeção de dados para O Cabeleireiro...")

        # 1. Business Info
        BusinessInfo.objects.all().delete()
        BusinessInfo.objects.create(
            name="O Cabeleireiro - Oficina Orgânica de Corte e Cor",
            address="Tv. da Légua da Póvoa 26A, 1250-037 Lisboa",
            phone="927704499",
            email="geral@ocabeleireiro.pt",
            schedule="Terça a Sexta-feira: 10:00–18:00\nSábado: 10:00–17:00\nDomingo e Segunda-feira: Encerrado",
            google_maps_url="https://maps.google.com/?q=Tv.+da+Légua+da+Póvoa+26A,+1250-037+Lisboa",
            description="Uma oficina orgânica de corte e cor, onde se produz ARTE e onde o NATURAL também é BELO. Utilizamos exclusivamente a marca Davines, representando a nossa filosofia orgânica, ecológica e sustentável."
        )
        self.stdout.write(self.style.SUCCESS('BusinessInfo criado com sucesso!'))

        # 2. Categorias
        ServiceCategory.objects.all().delete()
        cat_corte = ServiceCategory.objects.create(name="Corte e Styling", order=1)
        cat_cor = ServiceCategory.objects.create(name="Cor e Tratamentos", order=2)

        # 3. Serviços
        Service.objects.all().delete()
        servicos = [
            ("Corte Masculino", cat_corte, 20.00),
            ("Corte Masculino Junior (Até 20 anos)", cat_corte, 15.00),
            ("Corte Mulher sem Brushing", cat_corte, 33.00),
            ("Corte e Brushing Feminino", cat_corte, 43.00),
            ("Corte Infantil", cat_corte, 12.00),
            ("Franja", cat_corte, 8.00),
            ("Brushing", cat_corte, 20.00),
            ("Coloração", cat_cor, 43.00),
            ("Madeixas", cat_cor, 65.00),
            ("Hidratação", cat_cor, 15.00),
            ("Reconstrução Vegana / Botox", cat_cor, 30.00),
            ("Alisamento", cat_cor, 85.00),
        ]
        
        for nome, categoria, preco in servicos:
            Service.objects.create(name=nome, category=categoria, price=preco)

        # 4. Membros da Equipa
        StaffMember.objects.all().delete()
        StaffMember.objects.create(name="Mónica Dias", role="Cabeleireira")
        StaffMember.objects.create(name="Cristiano Napolitano", role="Colorista")
        
        # 5. Testemunhos
        Testimonial.objects.all().delete()
        Testimonial.objects.create(
            client_name="Sofia Ramos",
            text="Simplesmente o melhor corte que já tive. O conceito orgânico faz toda a diferença no brilho do cabelo.", 
            rating=5
        )
        Testimonial.objects.create(
            client_name="João Mendes",
            text="Espaço incrível em Lisboa. Profissionais de mão cheia.", 
            rating=5
        )

        self.stdout.write(self.style.SUCCESS('Dados dO Cabeleireiro injetados com sucesso!'))
