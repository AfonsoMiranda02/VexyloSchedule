from datetime import date, time
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from website.models import BusinessInfo, ServiceCategory, Service, StaffMember, Appointment

class SecurityAndXSSTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(username='admin_staff', email='admin@exemplo.com', password='Password123!')
        self.client.force_login(self.admin_user)
        
        self.business = BusinessInfo.objects.create(name="Salão", address="Rua", phone="900")
        self.category = ServiceCategory.objects.create(name="Cabelo")
        self.service = Service.objects.create(category=self.category, name="Corte Normal", price=Decimal('15.00'), duration=30)
        self.staff = StaffMember.objects.create(name="Staff Normal", role="Barbeiro")

    def test_malicious_client_name_in_calendar_api_is_safely_serialized(self):
        """Nomes de clientes com payloads XSS são transportados com segurança como JSON strings."""
        hostile_name = "<script>alert('XSS_ATTACK')</script>"
        malicious_user = User.objects.create_user(
            username='attacker', 
            first_name=hostile_name, 
            password='Password123!'
        )
        
        appt = Appointment.objects.create(
            user=malicious_user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 5, 10),
            time=time(10, 0),
            status='Confirmada'
        )
        
        calendar_api_url = reverse('api_calendar_events')
        response = self.client.get(calendar_api_url, {'start': '2026-05-01', 'end': '2026-05-31'})
        self.assertEqual(response.status_code, 200)
        
        events = response.json()
        self.assertTrue(len(events) >= 1)
        target_event = next(e for e in events if e['id'] == appt.id)
        
        # O extendedProps client_name contém a string pura (não interpretada como HTML)
        self.assertEqual(target_event['extendedProps']['client_name'], hostile_name)

    def test_admin_dashboard_get_request_is_side_effect_free(self):
        """O endpoint GET do dashboard analítico não deve alterar estados de marcações antigas."""
        past_user = User.objects.create_user(username='cliente_antigo', password='Password123!')
        
        # Marcação pendente de ontem
        appt = Appointment.objects.create(
            user=past_user,
            service=self.service,
            staff_member=self.staff,
            date=date(2026, 1, 1),
            time=time(10, 0),
            status='Pendente'
        )
        
        stats_url = reverse('admin_dashboard_stats')
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)
        
        # Garante que o status da marcação NÃO foi modificado pelo simples GET
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Pendente')
        self.assertNotEqual(appt.status, 'Concluída')

    def test_admin_calendar_template_uses_safe_dom_apis_and_no_innerhtml(self):
        """Regressão estática: o template do FullCalendar no admin deve usar textContent e nunca innerHTML/html injection."""
        import os
        from django.conf import settings

        template_path = os.path.join(settings.BASE_DIR, 'website', 'templates', 'admin', 'website', 'appointment', 'change_list.html')
        self.assertTrue(os.path.exists(template_path), f"Template {template_path} não encontrado.")

        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Proibir padrões vulneráveis
        self.assertNotIn('{ html:', content, "Template não deve usar FullCalendar { html: ... }")
        self.assertNotIn('innerHTML =', content, "Template não deve usar innerHTML.")
        self.assertNotIn('${props.client_name}', content, "Template não deve interpolar client_name diretamente em strings HTML.")
        self.assertNotIn('${props.service_name}', content, "Template não deve interpolar service_name diretamente em strings HTML.")

        # Garantir uso de APIs DOM seguras
        self.assertIn('textContent', content, "Template deve usar textContent para renderizar propriedades.")
        self.assertIn('createElement', content, "Template deve usar createElement para construir a árvore DOM.")
