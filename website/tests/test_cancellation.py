from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Appointment

class CancellationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username='dono', password='Password123!')
        self.other_user = User.objects.create_user(username='outro', password='Password123!')
        
        self.business = BusinessInfo.objects.create(
            name="Salão Teste",
            address="Rua Teste",
            phone="900000000",
            schedule="09:00 - 19:00",
            cancel_limit_hours=24
        )
        
        self.category = ServiceCategory.objects.create(name="Geral")
        self.service = Service.objects.create(
            category=self.category,
            name="Corte",
            price=Decimal('15.00'),
            duration=30
        )
        self.staff = StaffMember.objects.create(name="Barbeiro", role="Barbeiro")

    def test_owner_can_cancel_eligible_appointment(self):
        """O proprietário pode cancelar uma marcação dentro do prazo limite (ex: daqui a 48h)."""
        future_date = timezone.localdate() + timedelta(days=2)
        appt = Appointment.objects.create(
            user=self.owner,
            service=self.service,
            staff_member=self.staff,
            date=future_date,
            time=time(14, 0),
            status='Pendente'
        )
        
        self.client.force_login(self.owner)
        cancel_url = reverse('cancel_appointment', kwargs={'pk': appt.id})
        
        response = self.client.post(cancel_url, {
            'cancellation_reason': 'Mudança de planos',
            'cancellation_notes': 'Surgiu um compromisso'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Cancelada')
        self.assertEqual(appt.cancellation_reason, 'Mudança de planos')

    def test_other_user_cannot_cancel_appointment(self):
        """Um utilizador não pode cancelar a marcação de outro cliente."""
        future_date = timezone.localdate() + timedelta(days=2)
        appt = Appointment.objects.create(
            user=self.owner,
            service=self.service,
            staff_member=self.staff,
            date=future_date,
            time=time(14, 0),
            status='Pendente'
        )
        
        self.client.force_login(self.other_user)
        cancel_url = reverse('cancel_appointment', kwargs={'pk': appt.id})
        
        response = self.client.post(cancel_url, {'cancellation_reason': 'Teste'}, follow=True)
        # Deve retornar 404 porque get_object_or_404 filtra por user=request.user
        self.assertEqual(response.status_code, 404)
        
        appt.refresh_from_db()
        self.assertNotEqual(appt.status, 'Cancelada')

    def test_cancellation_within_limit_hours_rejected(self):
        """Cancelamento a menos de 24h do início da marcação deve ser bloqueado server-side."""
        # Marcação daqui a 2 horas (abaixo do cancel_limit_hours de 24h)
        near_future = timezone.now() + timedelta(hours=2)
        local_dt = timezone.localtime(near_future)
        
        appt = Appointment.objects.create(
            user=self.owner,
            service=self.service,
            staff_member=self.staff,
            date=local_dt.date(),
            time=local_dt.time(),
            status='Pendente'
        )
        
        self.client.force_login(self.owner)
        cancel_url = reverse('cancel_appointment', kwargs={'pk': appt.id})
        
        response = self.client.post(cancel_url, {'cancellation_reason': 'Tarde demais'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já não é possível cancelar esta marcação online")
        
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Pendente')

    def test_concluded_appointment_cannot_be_cancelled(self):
        """Marcação já concluída não pode ser cancelada."""
        future_date = timezone.localdate() + timedelta(days=2)
        appt = Appointment.objects.create(
            user=self.owner,
            service=self.service,
            staff_member=self.staff,
            date=future_date,
            time=time(14, 0),
            status='Concluída'
        )
        
        self.client.force_login(self.owner)
        cancel_url = reverse('cancel_appointment', kwargs={'pk': appt.id})
        
        response = self.client.post(cancel_url, {'cancellation_reason': 'Tentativa indevida'}, follow=True)
        self.assertEqual(response.status_code, 200)
        
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Concluída')

    def test_no_show_appointment_cannot_be_cancelled(self):
        """Marcação marcada como Faltou (No-Show) não pode ser cancelada."""
        future_date = timezone.localdate() + timedelta(days=2)
        appt = Appointment.objects.create(
            user=self.owner,
            service=self.service,
            staff_member=self.staff,
            date=future_date,
            time=time(14, 0),
            status='Faltou'
        )
        
        self.client.force_login(self.owner)
        cancel_url = reverse('cancel_appointment', kwargs={'pk': appt.id})
        
        response = self.client.post(cancel_url, {'cancellation_reason': 'Tentativa indevida'}, follow=True)
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Faltou')
