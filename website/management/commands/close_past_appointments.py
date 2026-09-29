from django.core.management.base import BaseCommand
from django.utils import timezone
from website.models import Appointment

class Command(BaseCommand):
    help = (
        'Processa marcações que já passaram da sua data/hora e que ainda estão Pendente/Confirmada. '
        'Suporta --dry-run e definição explícita do estado de destino para não fabricar desfechos.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista as marcações elegíveis sem alterar a base de dados.',
        )
        parser.add_argument(
            '--target-status',
            type=str,
            default='Concluída',
            choices=['Concluída', 'Faltou'],
            help='Estado para o qual as marcações elegíveis devem transitar (Concluída ou Faltou).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_status = options['target_status']
        hoje = timezone.localdate()
        hora_atual = timezone.localtime().time()

        # Marcações cuja data é anterior a hoje
        antigas = Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date__lt=hoje
        )
        
        # Marcações de hoje cuja hora de fim já passou
        hoje_passadas = Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date=hoje,
            end_time__lt=hora_atual
        )

        total_elegiveis = antigas.count() + hoje_passadas.count()

        if total_elegiveis == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma marcação passada pendente de resolução.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] Foram encontradas {total_elegiveis} marcação(ões) passadas elegíveis para transição para "{target_status}". '
                'Nenhuma alteração foi efetuada.'
            ))
            for apt in list(antigas) + list(hoje_passadas):
                self.stdout.write(f'  - #{apt.id}: {apt.date} {apt.time} ({apt.user.username} - {apt.effective_service_name}) [Atual: {apt.status}]')
            return

        total_atualizadas = 0
        if antigas.exists():
            total_atualizadas += antigas.update(status=target_status)
        if hoje_passadas.exists():
            total_atualizadas += hoje_passadas.update(status=target_status)

        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {total_atualizadas} marcação(ões) passadas foram atualizadas para "{target_status}".'
        ))
