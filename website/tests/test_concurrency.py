import threading
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from website.models import BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, StaffMember, Appointment
from website.services.booking import BookingService, BookingError

class ConcurrencyBookingTests(TransactionTestCase):
    """
    Testes de concorrência que simulam dois clientes a submeter exatamente
    o mesmo horário e profissional no mesmo milissegundo.
    """
    def setUp(self):
        self.user1 = User.objects.create_user(username='concorrente1', password='Password123!')
        self.user2 = User.objects.create_user(username='concorrente2', password='Password123!')
        
        self.business = BusinessInfo.objects.create(
            name="Salão Concorrente",
            address="Rua",
            phone="900",
            schedule="09-19"
        )
        for w in range(7):
            BusinessOpeningHours.objects.create(
                business=self.business,
                weekday=w,
                is_open=(w != 6),
                opening_time=time(9, 0),
                closing_time=time(19, 0)
            )
            
        self.category = ServiceCategory.objects.create(name="Cabelo")
        self.service = Service.objects.create(
            category=self.category,
            name="Corte Concorrência",
            price=Decimal('15.00'),
            duration=30
        )
        self.staff = StaffMember.objects.create(name="Barbeiro Concorrência", role="Barbeiro")

    def test_concurrent_double_booking_prevented(self):
        """Duas threads a disputar o mesmo slot com o mesmo profissional: apenas uma pode ter sucesso."""
        target_date = timezone.localdate() + timedelta(days=3)
        while target_date.weekday() == 6:
            target_date += timedelta(days=1)
            
        target_time = time(11, 30)
        
        results = []
        errors = []

        from django.db import connection

        if connection.vendor != 'postgresql':
            # Nota técnica: SQLite em memória (:memory:) isola a base de dados por thread.
            # O teste de concorrência com threads reais é executado em PostgreSQL (conforme configurado no CI).
            # Em SQLite, validamos a deteção estrita de colisão e integridade de slots:
            appt1 = BookingService.book_appointment(
                user=self.user1,
                service=self.service,
                target_date=target_date,
                start_time=target_time,
                staff_member=self.staff
            )
            self.assertIsNotNone(appt1.id)
            
            with self.assertRaises(BookingError):
                BookingService.book_appointment(
                    user=self.user2,
                    service=self.service,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=self.staff
                )
            return

        # Execução multi-thread real em PostgreSQL (com row-level locks select_for_update)
        def book_attempt(user):
            try:
                appt = BookingService.book_appointment(
                    user=user,
                    service=self.service,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=self.staff
                )
                results.append(appt)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=book_attempt, args=(self.user1,))
        t2 = threading.Thread(target=book_attempt, args=(self.user2,))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # O invariante fundamental: NUNCA podem existir duas marcações ativas no mesmo slot!
        active_appointments = Appointment.objects.filter(
            date=target_date,
            time=target_time,
            staff_member=self.staff
        ).exclude(status='Cancelada')

        self.assertEqual(
            active_appointments.count(), 1, 
            "ERRO CRÍTICO: Ocorreu um double-booking! Ambas as threads conseguiram agendar o mesmo horário."
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)

