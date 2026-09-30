from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember, Appointment, UserProfile
from website.services.booking import (
    BookingService, BookingError, BusinessClosedError, 
    InvalidSlotError, SlotOccupiedError, StaffUnavailableError
)

class BookingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='cliente1', email='cli1@exemplo.com', password='Password123!')
        now = timezone.now()
        UserProfile.objects.create(user=self.user, terms_accepted_at=now, privacy_policy_accepted_at=now)
        self.client.force_login(self.user)
        
        # Configurar Negócio
        self.business = BusinessInfo.objects.create(
            name="Salão Teste",
            address="Rua Teste, 1",
            phone="900000000",
            schedule="Segunda a Sábado 09:00 - 19:00",
            opening_time=time(9, 0),
            closing_time=time(19, 0),
            lunch_start=time(13, 0),
            lunch_end=time(14, 0),
            cancel_limit_hours=24
        )
        
        # Configurar Horários (0=Seg..5=Sáb aberto, 6=Dom fechado)
        for w in range(7):
            BusinessOpeningHours.objects.create(
                business=self.business,
                weekday=w,
                is_open=(w != 6),
                opening_time=time(9, 0),
                closing_time=time(19, 0),
                lunch_start=time(13, 0),
                lunch_end=time(14, 0)
            )

        self.category = ServiceCategory.objects.create(name="Cabelo", order=1)
        self.service_30 = Service.objects.create(
            category=self.category,
            name="Corte 30m",
            price=Decimal('15.00'),
            duration=30,
            is_active=True
        )
        self.service_60 = Service.objects.create(
            category=self.category,
            name="Corte Completo 60m",
            price=Decimal('25.00'),
            duration=60,
            is_active=True
        )
        
        self.staff1 = StaffMember.objects.create(name="Barbeiro A", role="Senior", is_active=True)
        self.staff2 = StaffMember.objects.create(name="Barbeiro B", role="Junior", is_active=True)

    def get_future_open_date(self) -> date:
        """Gera uma data futura num dia útil (não domingo)."""
        d = timezone.localdate() + timedelta(days=2)
        while d.weekday() == 6: # Domingo
            d += timedelta(days=1)
        return d

    def get_future_sunday(self) -> date:
        """Gera uma data futura que seja domingo."""
        d = timezone.localdate() + timedelta(days=1)
        while d.weekday() != 6:
            d += timedelta(days=1)
        return d

    def test_booking_normal_success(self):
        """Marcação normal e válida com profissional e horários corretos."""
        target_date = self.get_future_open_date()
        target_time = time(10, 0)
        
        appt = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=target_time,
            staff_member=self.staff1
        )
        
        self.assertIsNotNone(appt.id)
        self.assertEqual(appt.staff_member, self.staff1)
        self.assertEqual(appt.service_name_at_booking, "Corte 30m")
        self.assertEqual(appt.price_at_booking, Decimal('15.00'))
        self.assertEqual(appt.duration_at_booking, 30)
        self.assertEqual(appt.end_time, time(10, 30))

    def test_booking_in_past_rejected(self):
        """Marcação em data/hora no passado deve ser rejeitada."""
        past_date = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=past_date,
                start_time=time(10, 0),
                staff_member=self.staff1
            )

    def test_booking_on_closed_day_rejected(self):
        """Marcação num dia em que o estabelecimento está fechado (ex: Domingo) deve ser rejeitada."""
        sunday = self.get_future_sunday()
        with self.assertRaises(BusinessClosedError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=sunday,
                start_time=time(10, 0),
                staff_member=self.staff1
            )

    def test_booking_outside_opening_hours_rejected(self):
        """Marcação antes da abertura ou após o fecho deve ser rejeitada."""
        target_date = self.get_future_open_date()
        # Antes das 09:00
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(8, 30),
                staff_member=self.staff1
            )

    def test_booking_crossing_closing_time_rejected(self):
        """Serviço de 60m às 18:30 (fecho às 19:00) ultrapassa fecho e deve falhar."""
        target_date = self.get_future_open_date()
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_60,
                target_date=target_date,
                start_time=time(18, 30),
                staff_member=self.staff1
            )

    def test_booking_lunch_overlap_rejected(self):
        """Marcação que colide com o almoço (13:00 - 14:00) deve falhar."""
        target_date = self.get_future_open_date()
        # Marcação às 13:00
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(13, 0),
                staff_member=self.staff1
            )
        # Marcação às 12:45 com duração de 30 min (termina às 13:15, sobrepondo início do almoço)
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(12, 45),
                staff_member=self.staff1
            )

    def test_booking_occupied_staff_overlap_rejected(self):
        """Colisão de horário com o mesmo profissional deve ser rejeitada."""
        target_date = self.get_future_open_date()
        
        # 1. Cria marcação 10:00 - 10:30 para staff1
        BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(10, 0),
            staff_member=self.staff1
        )
        
        # 2. Tenta marcar no mesmo horário para o mesmo staff1
        with self.assertRaises(SlotOccupiedError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(10, 0),
                staff_member=self.staff1
            )

    def test_booking_interval_duration_overlap_rejected(self):
        """
        Intervalo sobreposto com horários de início diferentes deve colidir:
        Existente: 10:00 - 11:00 (60m)
        Tentativa: 10:30 - 11:00 (30m)
        """
        target_date = self.get_future_open_date()
        
        # 10:00 - 11:00
        BookingService.book_appointment(
            user=self.user,
            service=self.service_60,
            target_date=target_date,
            start_time=time(10, 0),
            staff_member=self.staff1
        )
        
        # 10:30 - 11:00 (sobrepõe a segunda metade)
        with self.assertRaises(SlotOccupiedError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(10, 30),
                staff_member=self.staff1
            )

    def test_cancelled_appointment_does_not_block_slot(self):
        """Marcação cancelada liberta o horário para novas marcações."""
        target_date = self.get_future_open_date()
        
        appt = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(11, 0),
            staff_member=self.staff1
        )
        appt.status = 'Cancelada'
        appt.save()
        
        # Agora o slot 11:00 com staff1 deve estar disponível novamente
        appt2 = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(11, 0),
            staff_member=self.staff1
        )
        self.assertEqual(appt2.status, 'Pendente')

    def test_any_staff_member_allocation(self):
        """Quando o cliente escolhe 'Qualquer Profissional', o sistema aloca o profissional livre."""
        target_date = self.get_future_open_date()
        
        # Ocupar staff1 às 15:00
        BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(15, 0),
            staff_member=self.staff1
        )
        
        # Pedir marcação às 15:00 sem especificar staff (deve alocar staff2)
        appt = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(15, 0),
            staff_member=None
        )
        self.assertEqual(appt.staff_member, self.staff2)

    def test_no_staff_available_rejected(self):
        """Se todos os profissionais estiverem ocupados, a marcação sem preferência é rejeitada."""
        target_date = self.get_future_open_date()
        
        # Ocupar staff1 e staff2 às 16:00
        BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(16, 0),
            staff_member=self.staff1
        )
        BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(16, 0),
            staff_member=self.staff2
        )
        
        with self.assertRaises(SlotOccupiedError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(16, 0),
                staff_member=None
            )

    def test_cross_midnight_booking_rejected(self):
        """Marcação às 23:45 com 30m ultrapassa a meia-noite e deve ser rejeitada."""
        target_date = self.get_future_open_date()
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(23, 45),
                staff_member=self.staff1
            )

    def test_closing_time_exact_boundaries(self):
        """
        18:45 + 30m termina às 19:15 (fecho às 19:00) -> rejeitada.
        18:30 + 30m termina às 19:00 (fecho às 19:00) -> permitida.
        """
        target_date = self.get_future_open_date()
        
        # 18:45 + 30m -> Rejeitado
        with self.assertRaises(InvalidSlotError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(18, 45),
                staff_member=self.staff1
            )

        # 18:30 + 30m -> Permitido
        appt = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(18, 30),
            staff_member=self.staff1
        )
        self.assertEqual(appt.end_time, time(19, 0))

    def test_zero_active_staff_raises_staff_unavailable_error(self):
        """Se não existirem profissionais ativos, marcação deve falhar e NUNCA criar staff=None."""
        StaffMember.objects.all().update(is_active=False)
        target_date = self.get_future_open_date()

        initial_count = Appointment.objects.count()
        with self.assertRaises(StaffUnavailableError):
            BookingService.book_appointment(
                user=self.user,
                service=self.service_30,
                target_date=target_date,
                start_time=time(10, 0),
                staff_member=None
            )
        self.assertEqual(Appointment.objects.count(), initial_count)

    def test_booking_slot_granularity_enforced(self):
        """Horários que não respeitam a granularidade de 30 minutos devem ser rejeitados."""
        target_date = self.get_future_open_date()
        for bad_time in [time(10, 7), time(10, 13), time(10, 29), time(11, 45)]:
            with self.assertRaises(InvalidSlotError):
                BookingService.book_appointment(
                    user=self.user,
                    service=self.service_30,
                    target_date=target_date,
                    start_time=bad_time,
                    staff_member=self.staff1
                )

    def test_admin_form_blocks_collision_and_allows_self_edit(self):
        """AppointmentAdminForm deve bloquear colisões e permitir editar a própria marcação sem colidir consigo mesma."""
        from website.forms import AppointmentAdminForm
        target_date = self.get_future_open_date()

        # Cria marcação 10:00 - 10:30 para staff1
        appt1 = BookingService.book_appointment(
            user=self.user,
            service=self.service_30,
            target_date=target_date,
            start_time=time(10, 0),
            staff_member=self.staff1
        )

        # Tentativa de criar nova marcação pelo Admin no mesmo horário e staff -> Inválido
        form_data = {
            'user': self.user.id,
            'service': self.service_30.id,
            'staff_member': self.staff1.id,
            'date': target_date,
            'time': time(10, 0),
            'status': 'Confirmada'
        }
        form = AppointmentAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Conflito de horário', str(form.errors))

        # Editar appt1 mantendo o mesmo horário -> Válido (exclui o próprio pk)
        edit_data = {
            'user': self.user.id,
            'service': self.service_30.id,
            'staff_member': self.staff1.id,
            'date': target_date,
            'time': time(10, 0),
            'status': 'Confirmada'
        }
        edit_form = AppointmentAdminForm(data=edit_data, instance=appt1)
        self.assertTrue(edit_form.is_valid(), edit_form.errors)

    def test_api_available_times_malformed_input_returns_400(self):
        """Pedidos com parâmetros inválidos para a API de horários disponíveis devem retornar HTTP 400."""
        url = reverse('api_available_times')
        
        # Data inválida
        res = self.client.get(url, {'service_id': self.service_30.id, 'date': 'data-invalida'})
        self.assertEqual(res.status_code, 400)

        # Serviço inválido
        res = self.client.get(url, {'service_id': '99999', 'date': '2026-05-10'})
        self.assertEqual(res.status_code, 400)

        # Staff ID inválido/inexistente explicitamente fornecido
        res = self.client.get(url, {'service_id': self.service_30.id, 'date': '2026-05-10', 'staff_id': '99999'})
        self.assertEqual(res.status_code, 400)
