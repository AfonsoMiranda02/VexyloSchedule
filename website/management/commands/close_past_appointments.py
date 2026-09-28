from django.core.management.base import BaseCommand
from django.utils import timezone
from website.models import Appointment

class Command(BaseCommand):
    help = 'Fecha automaticamente marcações antigas (Pendente/Confirmada) como Concluída.'

    def handle(self, *args, **kwargs):
        hoje = timezone.localdate()
        hora_atual = timezone.localtime().time()

        # Filtra marcações que precisam de ser fechadas
        # Data anterior a hoje
        antigas = Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date__lt=hoje
        )
        
        # Data igual a hoje mas hora de fim já passou
        hoje_passadas = Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date=hoje,
            end_time__lt=hora_atual
        )

        total_atualizadas = 0

        # Atualizar antigas
        if antigas.exists():
            total_atualizadas += antigas.update(status='Concluída')
            
        # Atualizar as de hoje que já passaram
        if hoje_passadas.exists():
            total_atualizadas += hoje_passadas.update(status='Concluída')

        if total_atualizadas > 0:
            self.stdout.write(self.style.SUCCESS(f'Sucesso: {total_atualizadas} marcações passadas foram marcadas como "Concluída".'))
        else:
            self.stdout.write(self.style.WARNING('Nenhuma marcação antiga pendente de fecho.'))
