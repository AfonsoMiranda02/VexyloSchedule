from decimal import Decimal
from datetime import date, time
from django.test import TestCase, override_settings
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

    def test_business_opening_hours_lunch_validation(self):
        """Validação de horários de almoço: ambos presentes ou ausentes, e estritamente dentro do horário de expediente."""
        business = BusinessInfo.objects.create(name="Empresa Horas", address="Rua H", phone="933333333", schedule="09-19")
        
        # 1. Apenas lunch_start definido -> Rejeitado
        h1 = BusinessOpeningHours(
            business=business, weekday=0, is_open=True,
            opening_time=time(9, 0), closing_time=time(19, 0),
            lunch_start=time(13, 0), lunch_end=None
        )
        with self.assertRaises(ValidationError):
            h1.clean()

        # 2. Início de almoço posterior ao fim -> Rejeitado
        h2 = BusinessOpeningHours(
            business=business, weekday=0, is_open=True,
            opening_time=time(9, 0), closing_time=time(19, 0),
            lunch_start=time(14, 0), lunch_end=time(13, 0)
        )
        with self.assertRaises(ValidationError):
            h2.clean()

        # 3. Almoço fora do horário de funcionamento (ex: 22:00 às 23:00) -> Rejeitado
        h3 = BusinessOpeningHours(
            business=business, weekday=0, is_open=True,
            opening_time=time(9, 0), closing_time=time(19, 0),
            lunch_start=time(22, 0), lunch_end=time(23, 0)
        )
        with self.assertRaises(ValidationError):
            h3.clean()

        # 4. Almoço válido (13:00 às 14:00) -> Permitido
        h_ok = BusinessOpeningHours(
            business=business, weekday=0, is_open=True,
            opening_time=time(9, 0), closing_time=time(19, 0),
            lunch_start=time(13, 0), lunch_end=time(14, 0)
        )
        h_ok.clean()
        h_ok.save()
        self.assertIsNotNone(h_ok.id)

    def test_seeder_idempotency_and_independent_bootstrap(self):
        """
        O comando seed_data deve ser idempotente e cada bloco deve ser independente:
        - Se já existir um superuser, o restante bootstrap (empresa, horários, serviços, staff) ainda assim é executado.
        - Executar duas vezes não duplica registos.
        - Se horários estiverem em falta, repara-os com segurança.
        """
        from django.core.management import call_command
        # Limpar estado
        BusinessInfo.objects.all().delete()
        Service.objects.all().delete()
        ServiceCategory.objects.all().delete()
        StaffMember.objects.all().delete()

        # Criar superutilizador antecipadamente
        User.objects.create_superuser(username='super_existente', password='Password123!')

        # 1. Primeira execução: mesmo com superuser existente, deve criar a empresa e serviços
        call_command('seed_data', with_demo=True)
        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(BusinessOpeningHours.objects.count(), 7)
        self.assertGreater(Service.objects.count(), 0)
        self.assertGreater(StaffMember.objects.count(), 0)

        counts_initial = {
            'business': BusinessInfo.objects.count(),
            'hours': BusinessOpeningHours.objects.count(),
            'categories': ServiceCategory.objects.count(),
            'services': Service.objects.count(),
            'staff': StaffMember.objects.count(),
        }

        # 2. Segunda execução imediata: idempotência estrita (nada é duplicado)
        call_command('seed_data', with_demo=True)
        counts_second = {
            'business': BusinessInfo.objects.count(),
            'hours': BusinessOpeningHours.objects.count(),
            'categories': ServiceCategory.objects.count(),
            'services': Service.objects.count(),
            'staff': StaffMember.objects.count(),
        }
        self.assertEqual(counts_initial, counts_second)

        # 3. Remoção parcial: apagar 2 dias de horários -> o seeder deve restaurar apenas os dias em falta
        BusinessOpeningHours.objects.filter(weekday__in=[2, 4]).delete()
        self.assertEqual(BusinessOpeningHours.objects.count(), 5)

        call_command('seed_data', with_demo=True)
        self.assertEqual(BusinessOpeningHours.objects.count(), 7)

    def test_production_cache_smoke_crud_and_timeout(self):
        """Validação de operações de leitura, escrita, incremento e expiração no cache."""
        from django.core.cache import cache
        import time as pytime

        test_key = "test_smoke_cache_key"
        cache.delete(test_key)

        # 1. Escrita com timeout curto de 1 segundo
        cache.set(test_key, 10, timeout=1)
        self.assertEqual(cache.get(test_key), 10)

        # 2. Incremento
        try:
            cache.incr(test_key)
            self.assertEqual(cache.get(test_key), 11)
        except ValueError:
            pass

        # 3. Timeout / Expiração
        pytime.sleep(1.1)
        self.assertIsNone(cache.get(test_key))

    @override_settings(DEBUG=False)
    def test_production_seeder_does_not_create_fake_services_or_staff(self):
        """Em modo de produção (DEBUG=False), o seed_data nunca cria serviços ou profissionais falsos."""
        from django.core.management import call_command
        BusinessInfo.objects.all().delete()
        Service.objects.all().delete()
        ServiceCategory.objects.all().delete()
        StaffMember.objects.all().delete()

        call_command('seed_data')

        # Em produção sem variáveis, não inventa catálogo nem staff
        self.assertEqual(Service.objects.count(), 0)
        self.assertEqual(StaffMember.objects.count(), 0)

    def test_migration_0007_preserves_custom_admin_opening_hours(self):
        """Garante que a nova migração 0007 não sobrescreve escolhas explícitas de horários do administrador."""
        business = BusinessInfo.objects.first()
        if not business:
            business = BusinessInfo.objects.create(name="Empresa Teste", phone="900000000", schedule="Horário")

        # Administrador configurou expressamente quarta-feira (2) como ABERTA
        wed, _ = BusinessOpeningHours.objects.get_or_create(
            business=business,
            weekday=2,
            defaults={'is_open': True, 'opening_time': time(9, 0), 'closing_time': time(19, 0)}
        )
        wed.is_open = True
        wed.save()

        import importlib
        mig_mod = importlib.import_module("website.migrations.0007_preserve_opening_hours_admin_choices")
        from django.apps import apps
        mig_mod.preserve_admin_opening_hours(apps, None)

        wed.refresh_from_db()
        self.assertTrue(wed.is_open, "A escolha do administrador para quarta-feira aberta deve ser estritamente preservada!")

    def test_verify_production_ready_command_semantics(self):
        """Validação do comportamento e categorias do comando verify_production_ready."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('verify_production_ready', stdout=out)
        output_str = out.getvalue()
        self.assertIn("A verificar integridade e prontidão de produção", output_str)
        self.assertIn("[1/2] Verificação da Infraestrutura Técnica:", output_str)
        self.assertIn("[2/2] Verificação da Configuração de Negócio:", output_str)
