from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.exceptions import ValidationError
from website.models import Appointment

class Command(BaseCommand):
    help = (
        'Processa marcações que já passaram da sua data/hora e que ainda estão Pendente/Confirmada. '
        'Por omissão move as marcações para o estado neutro "Aguardando Fecho" sem inferir sucesso ou falta.'
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
            default='Aguardando Fecho',
            choices=['Aguardando Fecho', 'Concluída', 'Faltou'],
            help='Estado para o qual as marcações passadas devem transitar (por omissão "Aguardando Fecho").',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_status = options['target_status']
        hoje = timezone.localdate()
        hora_atual = timezone.localtime().time()

        # Marcações cuja data é anterior a hoje
        antigas = list(Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date__lt=hoje
        ))
        
        # Marcações de hoje cuja hora de fim já passou
        hoje_passadas = list(Appointment.objects.filter(
            status__in=['Pendente', 'Confirmada'],
            date=hoje,
            end_time__lt=hora_atual
        ))

        elegiveis = antigas + hoje_passadas
        total_elegiveis = len(elegiveis)

        if total_elegiveis == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma marcação passada pendente de resolução.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] Foram encontradas {total_elegiveis} marcação(ões) passadas elegíveis para transição para "{target_status}". '
                'Nenhuma alteração foi efetuada.'
            ))
            for apt in elegiveis:
                self.stdout.write(f'  - #{apt.id}: {apt.date} {apt.time} ({apt.user.username} - {apt.effective_service_name}) [Atual: {apt.status}]')
            return

        total_atualizadas = 0
        for apt in elegiveis:
            try:
                apt.transition_to(target_status)
                apt.save()
                total_atualizadas += 1
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f'Erro na marcação #{apt.id}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {total_atualizadas} marcação(ões) passadas foram atualizadas para "{target_status}".'
        ))
