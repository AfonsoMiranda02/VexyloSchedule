"""
Domain Service de Agendamento do VexyloSchedule.
Responsável pela autoridade central de horários, cálculo de disponibilidade sem N+1,
alocação de profissionais com locks de concorrência (select_for_update) e criação
imutável de marcações com snapshots.
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from website.models import BusinessInfo, BusinessOpeningHours, Service, StaffMember, Appointment


class BookingError(Exception):
    """Exceção base de regras de negócio de agendamento."""
    pass


class BusinessClosedError(BookingError):
    """O estabelecimento está fechado no dia/hora solicitado."""
    pass


class InvalidSlotError(BookingError):
    """O horário solicitado é inválido, está no passado ou quebra regras do negócio."""
    pass


class SlotOccupiedError(BookingError):
    """O horário ou profissional solicitado já está ocupado."""
    pass


class StaffUnavailableError(BookingError):
    """Nenhum profissional elegível está disponível."""
    pass


class BookingService:
    SLOT_INTERVAL_MINUTES = 30

    @staticmethod
    def get_business_hours_for_date(target_date: date) -> Tuple[bool, time, time, Optional[time], Optional[time]]:
        """
        Retorna (is_open, opening_time, closing_time, lunch_start, lunch_end)
        para um determinado dia a partir de BusinessOpeningHours, com fallback em BusinessInfo.
        """
        weekday = target_date.weekday() # 0 = Segunda, 6 = Domingo
        business = BusinessInfo.get_solo()
        
        day_schedule = None
        if business and business.pk:
            day_schedule = BusinessOpeningHours.objects.filter(business=business, weekday=weekday).first()
        if day_schedule:
            return (
                day_schedule.is_open,
                day_schedule.opening_time,
                day_schedule.closing_time,
                day_schedule.lunch_start,
                day_schedule.lunch_end
            )
            
        # Fallback histórico seguro: Quarta-feira (2) e Domingo (6) fechados
        if weekday in (2, 6):
            return (False, time(9, 0), time(19, 0), None, None)
            
        return (
            True,
            business.opening_time if isinstance(business.opening_time, time) else time(9, 0),
            business.closing_time if isinstance(business.closing_time, time) else time(19, 0),
            business.lunch_start,
            business.lunch_end
        )

    @classmethod
    def get_available_slots(
        cls, 
        target_date: date, 
        service: Service, 
        staff_member: Optional[StaffMember] = None,
        slot_interval_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Calcula os blocos de horário disponíveis para uma data e serviço,
        otimizado com datetimes completos para evitar transição de meia-noite e N+1 queries.
        """
        is_open, open_time, close_time, lunch_st, lunch_et = cls.get_business_hours_for_date(target_date)
        if not is_open:
            return []

        duration = service.duration
        candidate_blocks: List[Tuple[time, time]] = []
        
        curr_dt = datetime.combine(target_date, open_time)
        close_dt = datetime.combine(target_date, close_time)

        lunch_start_dt = datetime.combine(target_date, lunch_st) if (lunch_st and lunch_et) else None
        lunch_end_dt = datetime.combine(target_date, lunch_et) if (lunch_st and lunch_et) else None

        while curr_dt + timedelta(minutes=duration) <= close_dt:
            slot_end_dt = curr_dt + timedelta(minutes=duration)

            # Rejeitar se ultrapassa a data (cross-midnight)
            if slot_end_dt.date() != target_date:
                break

            # Excluir se sobrepõe intervalo de almoço
            if lunch_start_dt and lunch_end_dt:
                if curr_dt < lunch_end_dt and slot_end_dt > lunch_start_dt:
                    curr_dt += timedelta(minutes=slot_interval_minutes)
                    continue

            candidate_blocks.append((curr_dt.time(), slot_end_dt.time()))
            curr_dt += timedelta(minutes=slot_interval_minutes)

        if not candidate_blocks:
            return []

        # 1 Query eficiente para todas as marcações ativas do dia
        day_appointments = list(
            Appointment.objects.filter(date=target_date)
            .exclude(status='Cancelada')
            .select_related('staff_member')
        )

        # Profissionais ativos
        staff_qs = StaffMember.objects.filter(is_active=True)
        if staff_member:
            staff_qs = staff_qs.filter(id=staff_member.id)
        active_staff = list(staff_qs)

        now = timezone.now()
        current_tz = timezone.get_current_timezone()
        result_slots = []

        for st, et in candidate_blocks:
            cand_start_dt = datetime.combine(target_date, st)
            cand_end_dt = cand_start_dt + timedelta(minutes=duration)

            slot_aware = timezone.make_aware(cand_start_dt, current_tz)
            is_past = slot_aware < now

            is_occupied = True
            if not is_past:
                if active_staff:
                    # Se houver pelo menos 1 profissional ativo sem colisão, o slot está livre
                    for staff in active_staff:
                        staff_apts = [a for a in day_appointments if a.staff_member_id == staff.id]
                        has_collision = False
                        for apt in staff_apts:
                            apt_start_dt = datetime.combine(apt.date, apt.time)
                            apt_end_dt = (
                                datetime.combine(apt.date, apt.end_time) 
                                if apt.end_time 
                                else (apt_start_dt + timedelta(minutes=apt.effective_duration))
                            )
                            if apt_start_dt < cand_end_dt and apt_end_dt > cand_start_dt:
                                has_collision = True
                                break
                        if not has_collision:
                            is_occupied = False
                            break
                else:
                    # Zero profissionais ativos disponíveis -> slot indisponível
                    is_occupied = True

            result_slots.append({
                'time': st.strftime('%H:%M'),
                'disabled': is_past or is_occupied,
                'reason': 'past' if is_past else ('occupied' if is_occupied else '')
            })

        return result_slots

    @classmethod
    @transaction.atomic
    def book_appointment(
        cls,
        user,
        service: Service,
        target_date: date,
        start_time: time,
        staff_member: Optional[StaffMember] = None,
        cancellation_notes: Optional[str] = None
    ) -> Appointment:
        """
        Reserva autoritativa com verificação server-side completa com datetimes
        e locks transacionais (select_for_update) contra concorrência e double-booking.
        """
        # 1. Validação de serviço ativo e duração
        if not service.is_active:
            raise InvalidSlotError("O serviço selecionado já não se encontra ativo para marcações.")

        duration = service.duration
        if duration < 5 or duration > 480:
            raise InvalidSlotError("Duração do serviço inválida (deve situar-se entre 5 e 480 minutos).")

        # 2. Validação da granularidade do slot (30 minutos)
        if (start_time.minute % cls.SLOT_INTERVAL_MINUTES != 0) or start_time.second != 0 or start_time.microsecond != 0:
            raise InvalidSlotError(f"Os agendamentos devem iniciar em intervalos de {cls.SLOT_INTERVAL_MINUTES} minutos.")

        # 3. Comparação rigorosa com datetimes completos (evita bugs de viragem de dia / cross-midnight)
        start_dt = datetime.combine(target_date, start_time)
        end_dt = start_dt + timedelta(minutes=duration)

        if end_dt.date() != target_date:
            raise InvalidSlotError("O agendamento ultrapassa o final do dia de funcionamento.")

        # 4. Validação de data/hora no passado
        current_tz = timezone.get_current_timezone()
        start_dt_aware = timezone.make_aware(start_dt, current_tz)
        if start_dt_aware < timezone.now():
            raise InvalidSlotError("Não é possível realizar agendamentos em horários passados.")

        # 5. Validação de horário de funcionamento do dia
        is_open, open_time, close_time, lunch_st, lunch_et = cls.get_business_hours_for_date(target_date)
        if not is_open:
            raise BusinessClosedError("O estabelecimento está encerrado na data selecionada.")

        open_dt = datetime.combine(target_date, open_time)
        close_dt = datetime.combine(target_date, close_time)

        if start_dt < open_dt or end_dt > close_dt or start_dt >= close_dt:
            raise InvalidSlotError("O serviço ultrapassa o horário de funcionamento do estabelecimento.")

        if lunch_st and lunch_et:
            lunch_start_dt = datetime.combine(target_date, lunch_st)
            lunch_end_dt = datetime.combine(target_date, lunch_et)
            if start_dt < lunch_end_dt and end_dt > lunch_start_dt:
                raise InvalidSlotError("O horário coincide com o período de intervalo/almoço.")

        # 6. Alocação e Lock Concorrente do Profissional
        assigned_staff: Optional[StaffMember] = None

        if staff_member:
            # Bloqueio exclusivo de linha (row-level lock) no profissional selecionado
            try:
                locked_staff = StaffMember.objects.select_for_update().get(id=staff_member.id, is_active=True)
            except StaffMember.DoesNotExist:
                raise StaffUnavailableError("O profissional selecionado não existe ou está inativo.")

            # Verifica colisões de horário usando datetimes
            existing_apts = list(
                Appointment.objects.filter(date=target_date, staff_member=locked_staff)
                .exclude(status='Cancelada')
            )
            for apt in existing_apts:
                apt_start_dt = datetime.combine(apt.date, apt.time)
                apt_end_dt = (
                    datetime.combine(apt.date, apt.end_time) 
                    if apt.end_time 
                    else (apt_start_dt + timedelta(minutes=apt.effective_duration))
                )
                if apt_start_dt < end_dt and apt_end_dt > start_dt:
                    raise SlotOccupiedError("O profissional selecionado já tem uma marcação confirmada ou pendente para este horário.")

            assigned_staff = locked_staff

        else:
            # "Qualquer Profissional" - Obter todos os profissionais ativos com lock ordenado para evitar Deadlocks
            all_active_ids = list(StaffMember.objects.filter(is_active=True).values_list('id', flat=True))
            if not all_active_ids:
                raise StaffUnavailableError("Não existem profissionais disponíveis para agendamento.")

            locked_candidates = list(
                StaffMember.objects.select_for_update().filter(id__in=all_active_ids).order_by('id')
            )
            
            day_apts = list(
                Appointment.objects.filter(date=target_date, staff_member__in=locked_candidates)
                .exclude(status='Cancelada')
            )

            for candidate in locked_candidates:
                candidate_apts = [a for a in day_apts if a.staff_member_id == candidate.id]
                collision = False
                for apt in candidate_apts:
                    apt_start_dt = datetime.combine(apt.date, apt.time)
                    apt_end_dt = (
                        datetime.combine(apt.date, apt.end_time) 
                        if apt.end_time 
                        else (apt_start_dt + timedelta(minutes=apt.effective_duration))
                    )
                    if apt_start_dt < end_dt and apt_end_dt > start_dt:
                        collision = True
                        break
                if not collision:
                    assigned_staff = candidate
                    break

            if not assigned_staff:
                raise SlotOccupiedError("Esse horário acabou de ser reservado. Por favor escolha outro horário.")

        # Invariante absoluta: Uma marcação nova de cliente NUNCA pode ter staff_member nulo
        if not assigned_staff:
            raise StaffUnavailableError("Não foi possível atribuir um profissional ao agendamento.")

        # 7. Criar a marcação com snapshots históricos
        appointment = Appointment.objects.create(
            user=user,
            service=service,
            staff_member=assigned_staff,
            date=target_date,
            time=start_time,
            end_time=end_dt.time(),
            status='Pendente',
            service_name_at_booking=service.name,
            price_at_booking=service.price,
            duration_at_booking=service.duration
        )

        return appointment

    @classmethod
    def save_admin_appointment(cls, appointment: Appointment) -> Appointment:
        """
        Guarda ou atualiza uma marcação a partir do Django Admin com autoridade transacional
        completa (select_for_update no staff), verificação de horário, granularidade,
        ausência de colisões e integridade de snapshots históricos.
        """
        with transaction.atomic():
            is_new = not appointment.pk
            target_date = appointment.date
            start_time = appointment.time
            service = appointment.service
            staff = appointment.staff_member

            if not service:
                raise InvalidSlotError("A marcação deve ter um serviço associado.")

            # Para novas marcações, o profissional é obrigatório
            if is_new and not staff:
                raise StaffUnavailableError("É obrigatório atribuir um profissional a novas marcações.")

            # Validação de serviço ativo:
            # Novas marcações rejeitam serviços inativos.
            # Se uma marcação existente alterar o serviço, o novo serviço também deve estar ativo.
            old_inst = None
            if not is_new:
                old_inst = Appointment.objects.filter(pk=appointment.pk).first()

            if is_new and not service.is_active:
                raise InvalidSlotError("O serviço selecionado não se encontra ativo para novas marcações.")
            if old_inst and old_inst.service_id != service.id and not service.is_active:
                raise InvalidSlotError("O novo serviço selecionado não se encontra ativo.")

            # Validação de horário no passado para novas marcações
            start_dt = datetime.combine(target_date, start_time)
            if is_new:
                current_tz = timezone.get_current_timezone()
                start_dt_aware = timezone.make_aware(start_dt, current_tz)
                if start_dt_aware < timezone.now():
                    raise InvalidSlotError("Não é possível realizar novos agendamentos em horários passados.")

            # Se for um registo legado sem profissional, permite guardar
            if not staff:
                appointment.save()
                return appointment

            # Bloqueio pessimista de concorrência ao nível de linha no profissional
            try:
                locked_staff = StaffMember.objects.select_for_update().get(id=staff.id)
            except StaffMember.DoesNotExist:
                raise StaffUnavailableError("O profissional selecionado não existe.")

            if not locked_staff.is_active and (is_new or (appointment.pk and Appointment.objects.filter(pk=appointment.pk, staff_member=locked_staff).count() == 0)):
                raise StaffUnavailableError(f"O profissional {locked_staff.name} está inativo para novas marcações.")

            # Granularidade (30 minutos)
            if (start_time.minute % cls.SLOT_INTERVAL_MINUTES != 0) or start_time.second != 0 or start_time.microsecond != 0:
                raise InvalidSlotError(f"Os agendamentos devem iniciar em intervalos de {cls.SLOT_INTERVAL_MINUTES} minutos.")

            # Duração e snapshots:
            # Regra de negócio explícita: A alteração de serviço no Admin constitui uma alteração formal
            # de reserva, atualizando expressamente os snapshots do serviço, preço e duração.
            if is_new or (old_inst and old_inst.service_id != service.id):
                duration = service.duration
                appointment.service_name_at_booking = service.name
                appointment.price_at_booking = service.price
                appointment.duration_at_booking = service.duration
            else:
                # Mantém os snapshots históricos originais e preserva a duração original
                duration = appointment.duration_at_booking or service.duration
                if not appointment.service_name_at_booking:
                    appointment.service_name_at_booking = service.name
                if appointment.price_at_booking is None:
                    appointment.price_at_booking = service.price
                if appointment.duration_at_booking is None:
                    appointment.duration_at_booking = duration

            end_dt = start_dt + timedelta(minutes=duration)

            if end_dt.date() != target_date:
                raise InvalidSlotError("O agendamento ultrapassa o final do dia de funcionamento.")

            # Horário de funcionamento do estabelecimento
            is_open, open_time, close_time, lunch_st, lunch_et = cls.get_business_hours_for_date(target_date)
            if not is_open:
                raise BusinessClosedError("O estabelecimento está encerrado na data selecionada.")

            open_dt = datetime.combine(target_date, open_time)
            close_dt = datetime.combine(target_date, close_time)

            if start_dt < open_dt or end_dt > close_dt or start_dt >= close_dt:
                raise InvalidSlotError("O serviço ultrapassa o horário de funcionamento do estabelecimento.")

            if lunch_st and lunch_et:
                lunch_start_dt = datetime.combine(target_date, lunch_st)
                lunch_end_dt = datetime.combine(target_date, lunch_et)
                if start_dt < lunch_end_dt and end_dt > lunch_start_dt:
                    raise InvalidSlotError("O horário coincide com o período de intervalo/almoço.")

            # Verificação atómica de colisão excluindo o próprio registo em caso de edição
            collision_qs = Appointment.objects.filter(
                date=target_date,
                staff_member=locked_staff
            ).exclude(status='Cancelada')

            if not is_new:
                collision_qs = collision_qs.exclude(pk=appointment.pk)

            for apt in collision_qs:
                apt_start_dt = datetime.combine(apt.date, apt.time)
                apt_end_dt = (
                    datetime.combine(apt.date, apt.end_time)
                    if apt.end_time
                    else (apt_start_dt + timedelta(minutes=apt.effective_duration))
                )
                if apt_start_dt < end_dt and apt_end_dt > start_dt:
                    raise SlotOccupiedError(
                        f"Conflito de horário: O profissional {locked_staff.name} já tem uma marcação ({apt.status}) "
                        f"das {apt.time.strftime('%H:%M')} às {apt_end_dt.time().strftime('%H:%M')}."
                    )

            appointment.end_time = end_dt.time()
            appointment.save()
            return appointment
