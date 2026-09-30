import os
import threading
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import connection
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember, Appointment
from website.services.booking import BookingService, BookingError, SlotOccupiedError

class ConcurrencyBookingTests(TransactionTestCase):
    """
    Testes de concorrência com threads simultâneas sincronizadas via threading.Barrier.
    Garante que sob race conditions em PostgreSQL com row-level locks (select_for_update),
    apenas uma reserva sobrevive e a outra é rejeitada com erro de domínio.
    """
    def setUp(self):
        self.user1 = User.objects.create_user(username='concorrente1', password='Password123!')
        self.user2 = User.objects.create_user(username='concorrente2', password='Password123!')
        
        self.business = BusinessInfo.objects.create(
            name="Salão Concorrente",
            address="Rua da Concorrência, 1",
            phone="900000000",
            schedule="Segunda a Sábado: 09:00 - 19:00"
        )
        for w in range(7):
            BusinessOpeningHours.objects.create(
                business=self.business,
                weekday=w,
                is_open=(w not in (2, 6)),
                opening_time=time(9, 0),
                closing_time=time(19, 0)
            )
            
        self.category = ServiceCategory.objects.create(name="Cabelo")
        self.service30 = Service.objects.create(
            category=self.category,
            name="Corte 30min",
            price=Decimal('15.00'),
            duration=30
        )
        self.service60 = Service.objects.create(
            category=self.category,
            name="Corte + Barba 60min",
            price=Decimal('25.00'),
            duration=60
        )
        self.staff1 = StaffMember.objects.create(name="Barbeiro A", role="Barbeiro", is_active=True)

    def _get_target_date(self):
        target_date = timezone.localdate() + timedelta(days=3)
        while target_date.weekday() in (2, 6): # Quarta e Domingo fechados
            target_date += timedelta(days=1)
        return target_date

    def test_concurrent_identical_slot_race(self):
        """Duas threads disputam o mesmo slot (10:00 - 10:30) com o mesmo profissional."""
        if os.getenv("CI_POSTGRES_REQUIRED") == "true":
            self.assertEqual(connection.vendor, "postgresql", "CI_POSTGRES_REQUIRED=true está ativo mas a base de dados não é PostgreSQL!")

        target_date = self._get_target_date()
        target_time = time(10, 0)

        if connection.vendor != 'postgresql':
            # SQLite em memória isola tabelas por thread; teste sequencial de colisão
            appt1 = BookingService.book_appointment(
                user=self.user1,
                service=self.service30,
                target_date=target_date,
                start_time=target_time,
                staff_member=self.staff1
            )
            self.assertIsNotNone(appt1.id)
            with self.assertRaises(BookingError):
                BookingService.book_appointment(
                    user=self.user2,
                    service=self.service30,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=self.staff1
                )
            return

        # Execução real com PostgreSQL e threading.Barrier
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def race_worker(user):
            connection.close() # Abre conexão isolada para esta thread
            try:
                barrier.wait(timeout=5)
                appt = BookingService.book_appointment(
                    user=user,
                    service=self.service30,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=self.staff1
                )
                results.append(appt)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=race_worker, args=(self.user1,))
        t2 = threading.Thread(target=race_worker, args=(self.user2,))

        t1.start()
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        active_appointments = Appointment.objects.filter(
            date=target_date,
            time=target_time,
            staff_member=self.staff1
        ).exclude(status='Cancelada')

        self.assertEqual(active_appointments.count(), 1, "Double booking detectado em PostgreSQL!")
        self.assertEqual(len(results), 1, "Exatamente 1 reserva deve ter sucesso.")
        self.assertEqual(len(errors), 1, "Exatamente 1 reserva deve falhar por colisão.")

    def test_concurrent_overlapping_durations_race(self):
        """
        Thread 1 pede 10:00-11:00 (60min).
        Thread 2 pede 10:30-11:00 (30min).
        Mesmo com horas de início distintas, sobrepõem-se no intervalo 10:30-11:00.
        Apenas uma pode suceder.
        """
        target_date = self._get_target_date()

        if connection.vendor != 'postgresql':
            appt1 = BookingService.book_appointment(
                user=self.user1,
                service=self.service60,
                target_date=target_date,
                start_time=time(10, 0),
                staff_member=self.staff1
            )
            self.assertIsNotNone(appt1.id)
            with self.assertRaises(BookingError):
                BookingService.book_appointment(
                    user=self.user2,
                    service=self.service30,
                    target_date=target_date,
                    start_time=time(10, 30),
                    staff_member=self.staff1
                )
            return

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker_60():
            connection.close()
            try:
                barrier.wait(timeout=5)
                appt = BookingService.book_appointment(
                    user=self.user1,
                    service=self.service60,
                    target_date=target_date,
                    start_time=time(10, 0),
                    staff_member=self.staff1
                )
                results.append(appt)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        def worker_30():
            connection.close()
            try:
                barrier.wait(timeout=5)
                appt = BookingService.book_appointment(
                    user=self.user2,
                    service=self.service30,
                    target_date=target_date,
                    start_time=time(10, 30),
                    staff_member=self.staff1
                )
                results.append(appt)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=worker_60)
        t2 = threading.Thread(target=worker_30)

        t1.start()
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        active = Appointment.objects.filter(
            date=target_date,
            staff_member=self.staff1
        ).exclude(status='Cancelada')

        self.assertEqual(active.count(), 1, "Sobrecarga de intervalo concorrente detectada!")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)

    def test_concurrent_any_staff_race_with_single_available_professional(self):
        """
        Ambos os utilizadores pedem 'Qualquer Profissional' às 11:00 para o mesmo dia,
        havendo apenas 1 profissional cadastrado.
        Apenas 1 utilizador pode obter a vaga.
        """
        target_date = self._get_target_date()
        target_time = time(11, 0)

        if connection.vendor != 'postgresql':
            appt1 = BookingService.book_appointment(
                user=self.user1,
                service=self.service30,
                target_date=target_date,
                start_time=target_time,
                staff_member=None
            )
            self.assertIsNotNone(appt1.id)
            self.assertEqual(appt1.staff_member, self.staff1)

            with self.assertRaises(BookingError):
                BookingService.book_appointment(
                    user=self.user2,
                    service=self.service30,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=None
                )
            return

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def race_worker(user):
            connection.close()
            try:
                barrier.wait(timeout=5)
                appt = BookingService.book_appointment(
                    user=user,
                    service=self.service30,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=None
                )
                results.append(appt)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        t1 = threading.Thread(target=race_worker, args=(self.user1,))
        t2 = threading.Thread(target=race_worker, args=(self.user2,))

        t1.start()
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        active = Appointment.objects.filter(
            date=target_date,
            time=target_time
        ).exclude(status='Cancelada')

        self.assertEqual(active.count(), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)

    def test_concurrent_admin_vs_public_booking_race(self):
        """
        Corrida concorrente: Administrador tenta criar/agendar marcação via
        BookingService.save_admin_appointment enquanto um cliente público tenta reservar o mesmo
        horário via BookingService.book_appointment com select_for_update.
        Exatamente UMA deve ter sucesso e a outra deve ser rejeitada.
        """
        target_date = self._get_target_date()
        target_time = time(14, 0)
        admin_user = User.objects.create_superuser(username='admin_concorrente', password='Password123!')

        if connection.vendor != 'postgresql':
            # Em SQLite, testa a validação transacional sequencial
            appt1 = BookingService.book_appointment(
                user=self.user1,
                service=self.service30,
                target_date=target_date,
                start_time=target_time,
                staff_member=self.staff1
            )
            self.assertIsNotNone(appt1.id)

            admin_appt = Appointment(
                user=admin_user,
                service=self.service30,
                staff_member=self.staff1,
                date=target_date,
                time=target_time,
                status='Confirmada'
            )
            with self.assertRaises(BookingError):
                BookingService.save_admin_appointment(admin_appt)
            return

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def admin_worker():
            connection.close()
            try:
                barrier.wait(timeout=5)
                admin_appt = Appointment(
                    user=admin_user,
                    service=self.service30,
                    staff_member=self.staff1,
                    date=target_date,
                    time=target_time,
                    status='Confirmada'
                )
                saved = BookingService.save_admin_appointment(admin_appt)
                results.append(('admin', saved))
            except Exception as e:
                errors.append(('admin', e))
            finally:
                connection.close()

        def public_worker():
            connection.close()
            try:
                barrier.wait(timeout=5)
                public_appt = BookingService.book_appointment(
                    user=self.user1,
                    service=self.service30,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=self.staff1
                )
                results.append(('public', public_appt))
            except Exception as e:
                errors.append(('public', e))
            finally:
                connection.close()

        t_admin = threading.Thread(target=admin_worker)
        t_public = threading.Thread(target=public_worker)

        t_admin.start()
        t_public.start()

        t_admin.join(timeout=10)
        t_public.join(timeout=10)

        active = Appointment.objects.filter(
            date=target_date,
            time=target_time,
            staff_member=self.staff1
        ).exclude(status='Cancelada')

        self.assertEqual(active.count(), 1, "Exatamente UMA marcação deve sobreviver à colisão Admin vs Público!")
        self.assertEqual(len(results), 1, "Exatamente um processo deve ter sucesso!")
        self.assertEqual(len(errors), 1, "Exatamente um processo deve falhar com BookingError!")
        self.assertIsInstance(errors[0][1], BookingError)
