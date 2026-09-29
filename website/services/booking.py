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
from django.core.exceptions import ValidationError
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
    @staticmethod
    def get_business_hours_for_date(target_date: date) -> Tuple[bool, time, time, Optional[time], Optional[time]]:
        """
        Retorna (is_open, opening_time, closing_time, lunch_start, lunch_end)
        para um determinado dia a partir de BusinessOpeningHours, com fallback em BusinessInfo.
        """
        weekday = target_date.weekday() # 0 = Segunda, 6 = Domingo
        business = BusinessInfo.get_solo()
        
        day_schedule = BusinessOpeningHours.objects.filter(business=business, weekday=weekday).first()
        if day_schedule:
            return (
                day_schedule.is_open,
                day_schedule.opening_time,
                day_schedule.closing_time,
                day_schedule.lunch_start,
                day_schedule.lunch_end
            )
            
        # Fallback histórico: Domingo fechado
        if weekday == 6:
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
        otimizado para evitar N+1 queries.
        """
        is_open, open_time, close_time, lunch_st, lunch_et = cls.get_business_hours_for_date(target_date)
        if not is_open:
            return []

        duration = service.duration
        candidate_blocks: List[Tuple[time, time]] = []
        
        curr_dt = datetime.combine(target_date, open_time)
        close_dt = datetime.combine(target_date, close_time)

        while curr_dt + timedelta(minutes=duration) <= close_dt:
            st = curr_dt.time()
            et = (curr_dt + timedelta(minutes=duration)).time()

            # Excluir se sobrepõe almoço
            if lunch_st and lunch_et:
                if st < lunch_et and et > lunch_st:
                    curr_dt += timedelta(minutes=slot_interval_minutes)
                    continue

            candidate_blocks.append((st, et))
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
            slot_aware = timezone.make_aware(datetime.combine(target_date, st), current_tz)
            is_past = slot_aware < now

            is_occupied = True
            if not is_past:
                if active_staff:
                    # Se houver pelo menos 1 profissional ativo sem colisão, o slot está livre
                    for staff in active_staff:
                        staff_apts = [a for a in day_appointments if a.staff_member_id == staff.id]
                        has_collision = False
                        for apt in staff_apts:
                            apt_st = apt.time
                            apt_et = apt.end_time or (datetime.combine(target_date, apt.time) + timedelta(minutes=apt.effective_duration)).time()
                            if apt_st < et and apt_et > st:
                                has_collision = True
                                break
                        if not has_collision:
                            is_occupied = False
                            break
                else:
                    # Fallback caso não existam profissionais cadastrados
                    has_collision = False
                    for apt in day_appointments:
                        apt_st = apt.time
                        apt_et = apt.end_time or (datetime.combine(target_date, apt.time) + timedelta(minutes=apt.effective_duration)).time()
                        if apt_st < et and apt_et > st:
                            has_collision = True
                            break
                    is_occupied = has_collision

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
        Reserva autoritativa com verificação server-side e locks transacionais (select_for_update)
        contra concorrência e double-booking.
        """
        # 1. Validação de serviço ativo
        if not service.is_active:
            raise InvalidSlotError("O serviço selecionado já não se encontra ativo para marcações.")

        duration = service.duration
        end_time = (datetime.combine(target_date, start_time) + timedelta(minutes=duration)).time()

        # 2. Validação de data/hora no passado
        current_tz = timezone.get_current_timezone()
        slot_dt = timezone.make_aware(datetime.combine(target_date, start_time), current_tz)
        if slot_dt < timezone.now():
            raise InvalidSlotError("Não é possível realizar agendamentos em horários passados.")

        # 3. Validação de horário de funcionamento do dia
        is_open, open_time, close_time, lunch_st, lunch_et = cls.get_business_hours_for_date(target_date)
        if not is_open:
            raise BusinessClosedError("O estabelecimento está encerrado na data selecionada.")

        if start_time < open_time or end_time > close_time:
            raise InvalidSlotError("O serviço ultrapassa o horário de funcionamento do estabelecimento.")

        if lunch_st and lunch_et:
            if start_time < lunch_et and end_time > lunch_st:
                raise InvalidSlotError("O horário coincide com o período de intervalo/almoço.")

        # 4. Alocação e Lock Concorrente do Profissional
        assigned_staff: Optional[StaffMember] = None

        if staff_member:
            # Bloqueio exclusivo de linha (row-level lock) no profissional selecionado
            try:
                locked_staff = StaffMember.objects.select_for_update().get(id=staff_member.id, is_active=True)
            except StaffMember.DoesNotExist:
                raise StaffUnavailableError("O profissional selecionado não existe ou está inativo.")

            # Verifica colisões de horário
            existing_apts = list(
                Appointment.objects.filter(date=target_date, staff_member=locked_staff)
                .exclude(status='Cancelada')
            )
            for apt in existing_apts:
                apt_st = apt.time
                apt_et = apt.end_time or (datetime.combine(target_date, apt.time) + timedelta(minutes=apt.effective_duration)).time()
                if apt_st < end_time and apt_et > start_time:
                    raise SlotOccupiedError("O profissional selecionado já tem uma marcação confirmada ou pendente para este horário.")

            assigned_staff = locked_staff

        else:
            # "Qualquer Profissional" - Obter todos os profissionais ativos com lock ordenado para evitar Deadlocks
            all_active_ids = list(StaffMember.objects.filter(is_active=True).values_list('id', flat=True))
            if not all_active_ids:
                # Se não houver nenhum profissional cadastrado, verifica colisão geral
                existing_apts = list(Appointment.objects.filter(date=target_date).exclude(status='Cancelada'))
                for apt in existing_apts:
                    apt_st = apt.time
                    apt_et = apt.end_time or (datetime.combine(target_date, apt.time) + timedelta(minutes=apt.effective_duration)).time()
                    if apt_st < end_time and apt_et > start_time:
                        raise SlotOccupiedError("Este horário já se encontra preenchido.")
                assigned_staff = None
            else:
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
                        apt_st = apt.time
                        apt_et = apt.end_time or (datetime.combine(target_date, apt.time) + timedelta(minutes=apt.effective_duration)).time()
                        if apt_st < end_time and apt_et > start_time:
                            collision = True
                            break
                    if not collision:
                        assigned_staff = candidate
                        break

                if not assigned_staff:
                    raise SlotOccupiedError("Não há nenhum profissional disponível no horário pretendido. Por favor selecione outro horário.")

        # 5. Criar a marcação com snapshots históricos
        appointment = Appointment.objects.create(
            user=user,
            service=service,
            staff_member=assigned_staff,
            date=target_date,
            time=start_time,
            end_time=end_time,
            status='Pendente',
            service_name_at_booking=service.name,
            price_at_booking=service.price,
            duration_at_booking=service.duration
        )

        return appointment
