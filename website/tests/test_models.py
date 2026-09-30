from decimal import Decimal
from datetime import date, time
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.contrib.auth.models import User
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember, Appointment, Testimonial

class ModelInvariantsAndHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='Password123!')
        self.category = ServiceCategory.objects.create(name="Cabelo", order=1)
        self.service = Service.objects.create(
            category=self.category,
            name="Corte Tradicional",
            price=Decimal('15.00'),
            duration=30
        )
        self.staff = StaffMember.objects.create(name="Carlos Barbeiro", role="Barbeiro")

    def test_negative_price_rejected_by_clean(self):
        """Preço negativo deve disparar ValidationError no clean()."""
        svc = Service(category=self.category, name="Preço Inválido", price=Decimal('-10.00'), duration=30)
        with self.assertRaises(ValidationError):
            svc.clean()

    def test_zero_or_negative_duration_rejected_by_clean(self):
        """Duração zero ou negativa deve disparar ValidationError no clean()."""
        svc = Service(category=self.category, name="Duração Inválida", price=Decimal('10.00'), duration=0)
        with self.assertRaises(ValidationError):
            svc.clean()

    def test_testimonial_rating_range_validated(self):
        """Classificação de testemunho deve estar entre 1 e 5."""
        t_bad = Testimonial(client_name="Cliente", text="Muito bom", rating=6)
        with self.assertRaises(ValidationError):
            t_bad.clean()
            
        t_bad_low = Testimonial(client_name="Cliente", text="Muito bom", rating=0)
        with self.assertRaises(ValidationError):
            t_bad_low.clean()

    def test_appointment_snapshots_preserve_history(self):
        """Alteração futura de preço/nome no serviço não altera o snapshot da marcação histórica."""
        appt = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 1, 15),
            time=time(10, 0)
        )
        
        self.assertEqual(appt.service_name_at_booking, "Corte Tradicional")
        self.assertEqual(appt.price_at_booking, Decimal('15.00'))
        self.assertEqual(appt.duration_at_booking, 30)
        
        # Agora o serviço sofre aumento de preço e mudança de nome 5 meses depois
        self.service.name = "Corte Premium 2026"
        self.service.price = Decimal('22.50')
        self.service.duration = 45
        self.service.save()
        
        appt.refresh_from_db()
        # O snapshot histórico da marcação de janeiro permanece intacto!
        self.assertEqual(appt.service_name_at_booking, "Corte Tradicional")
        self.assertEqual(appt.price_at_booking, Decimal('15.00'))
        self.assertEqual(appt.duration_at_booking, 30)
        self.assertEqual(appt.effective_service_name, "Corte Tradicional")
        self.assertEqual(appt.effective_price, Decimal('15.00'))

    def test_deletion_of_service_with_appointments_is_protected(self):
        """Tentar apagar um serviço que tem marcações históricas deve disparar ProtectedError."""
        Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 2, 1),
            time=time(11, 0)
        )
        
        with self.assertRaises(ProtectedError):
            self.service.delete()

    def test_deactivation_preserves_historical_records(self):
        """Desativar um serviço ou profissional preserva as marcações históricas intactas."""
        appt = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 2, 1),
            time=time(11, 0)
        )
        
        self.service.is_active = False
        self.service.save()
        self.staff.is_active = False
        self.staff.save()
        
        appt.refresh_from_db()
        self.assertEqual(appt.service.is_active, False)
        self.assertEqual(appt.staff_member.is_active, False)
        self.assertEqual(appt.effective_service_name, "Corte Tradicional")

    def test_business_info_singleton(self):
        """BusinessInfo deve comportar-se como singleton, impedindo a criação de um segundo registo."""
        b1 = BusinessInfo.objects.create(
            name="Empresa A",
            address="Rua A",
            phone="911111111",
            schedule="09-19"
        )
        
        # Tentativa de criar uma segunda instância deve falhar com ValidationError
        b2 = BusinessInfo(
            name="Empresa B",
            address="Rua B",
            phone="922222222",
            schedule="09-19"
        )
        with self.assertRaises(ValidationError):
            b2.save()
        
        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(BusinessInfo.objects.first().name, "Empresa A")

    def test_state_machine_aguardando_fecho_and_invalid_transitions(self):
        """Testa o novo estado 'Aguardando Fecho' e bloqueio de transições inválidas."""
        appt = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 3, 10),
            time=time(10, 0),
            status='Confirmada'
        )

        # Transição válida: Confirmada -> Aguardando Fecho
        appt.transition_to('Aguardando Fecho')
        appt.save()
        self.assertEqual(appt.status, 'Aguardando Fecho')

        # Transição válida: Aguardando Fecho -> Concluída
        appt.transition_to('Concluída')
        appt.save()
        self.assertEqual(appt.status, 'Concluída')

        # Transição inválida: Concluída -> Pendente
        with self.assertRaises(ValidationError):
            appt.transition_to('Pendente')

        # Transição inválida: Cancelada -> Confirmada
        appt.status = 'Cancelada'
        with self.assertRaises(ValidationError):
            appt.transition_to('Confirmada')

    def test_close_past_appointments_moves_to_aguardando_fecho(self):
        """O comando de encerramento deve mover marcações passadas para 'Aguardando Fecho' e não inferir 'Concluída'."""
        from django.core.management import call_command
        past_appt = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2020, 1, 1),
            time=time(10, 0),
            status='Confirmada'
        )

        call_command('close_past_appointments')
        past_appt.refresh_from_db()
        self.assertEqual(past_appt.status, 'Aguardando Fecho')

    def test_business_info_get_solo_does_not_mutate_db_on_read(self):
        """Chamar get_solo() quando não há registo deve retornar uma instância não gravada sem mutar a BD."""
        BusinessInfo.objects.all().delete()
        self.assertEqual(BusinessInfo.objects.count(), 0)

        solo = BusinessInfo.get_solo()
        self.assertEqual(solo.name, "VexyloSchedule")
        self.assertIsNone(solo.pk)
        # Garante que a BD continua vazia após o read
        self.assertEqual(BusinessInfo.objects.count(), 0)

    def test_appointment_protect_on_user_and_staff_delete(self):
        """Eliminar User ou StaffMember com marcações históricas deve disparar ProtectedError."""
        appt = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 4, 1),
            time=time(14, 0)
        )

        # Deletar staff com marcação -> ProtectedError
        with self.assertRaises(ProtectedError):
            self.staff.delete()

        # Deletar user com marcação -> ProtectedError
        with self.assertRaises(ProtectedError):
            self.user.delete()
