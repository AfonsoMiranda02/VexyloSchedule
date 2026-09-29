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
        """BusinessInfo deve comportar-se como singleton, atualizando o registo em vez de duplicar."""
        b1 = BusinessInfo.objects.create(
            name="Empresa A",
            address="Rua A",
            phone="911111111",
            schedule="09-19"
        )
        
        # Tentativa de criar uma segunda instância
        b2 = BusinessInfo(
            name="Empresa B",
            address="Rua B",
            phone="922222222",
            schedule="09-19"
        )
        b2.save()
        
        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(BusinessInfo.objects.first().name, "Empresa B")
