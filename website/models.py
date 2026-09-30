from django.db import models
from django.contrib.auth.models import User
from datetime import time, datetime, date, timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, CheckConstraint, Index
from django.utils import timezone

class Utilizador(User):
    class Meta:
        proxy = True
        verbose_name = "Utilizador"
        verbose_name_plural = "Utilizadores"

class BusinessInfo(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nome da Empresa")
    address = models.CharField(max_length=255, verbose_name="Morada")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    phone = models.CharField(max_length=50, verbose_name="Telefone")
    whatsapp = models.CharField(max_length=50, blank=True, null=True, verbose_name="WhatsApp")
    nif = models.CharField(max_length=20, null=True, blank=True, verbose_name="NIF")
    schedule = models.TextField(verbose_name="Horário de Funcionamento")
    
    # Horários padrão / fallback para cálculo de disponibilidade
    opening_time = models.TimeField(default="09:00:00", verbose_name="Hora de Abertura Padrão")
    closing_time = models.TimeField(default="19:00:00", verbose_name="Hora de Fecho Padrão")
    lunch_start = models.TimeField(blank=True, null=True, verbose_name="Início Almoço")
    lunch_end = models.TimeField(blank=True, null=True, verbose_name="Fim Almoço")
    
    google_maps_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link do Google Maps")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição da Empresa")
    cancel_limit_hours = models.IntegerField(
        default=24, 
        validators=[MinValueValidator(0), MaxValueValidator(168)],
        verbose_name="Horas limite para cancelamento (Ex: 24 para 24h antes)"
    )

    def clean(self):
        super().clean()
        if self.lunch_start and self.lunch_end:
            if self.lunch_start >= self.lunch_end:
                raise ValidationError({"lunch_start": "O início do almoço deve ser anterior ao fim do almoço."})
        if self.cancel_limit_hours is not None and (self.cancel_limit_hours < 0 or self.cancel_limit_hours > 168):
            raise ValidationError({"cancel_limit_hours": "O limite de cancelamento deve situar-se entre 0 e 168 horas."})

    def save(self, *args, **kwargs):
        self.clean()
        # Singleton pattern garantido: impede criação de um segundo registo
        if not self.pk:
            if BusinessInfo.objects.exists():
                raise ValidationError("Já existe uma configuração de empresa registada (Singleton).")
            self.pk = 1
        else:
            self.pk = 1
        from django.db import IntegrityError
        try:
            super().save(*args, **kwargs)
        except IntegrityError:
            raise ValidationError("Já existe uma configuração de empresa registada (Singleton).")

    @classmethod
    def get_solo(cls):
        """Retorna a instância singleton ou uma instância não-salva em memória sem mutar a BD em leituras GET."""
        info = cls.objects.first()
        if not info:
            from django.conf import settings
            if not getattr(settings, 'DEBUG', True):
                return cls(
                    name="VexyloSchedule",
                    address="Configuração em curso",
                    phone="",
                    whatsapp="",
                    schedule="Horário a definir no painel de administração",
                    opening_time=time(9, 0),
                    closing_time=time(19, 0),
                    cancel_limit_hours=24
                )
            return cls(
                name="VexyloSchedule",
                address="Morada a definir",
                phone="900000000",
                whatsapp="900000000",
                schedule="Segunda a Sábado (Quarta e Domingo encerrado): 09:00 - 19:00",
                opening_time=time(9, 0),
                closing_time=time(19, 0),
                cancel_limit_hours=24
            )
        return info

    @property
    def clean_whatsapp(self):
        """Retorna o número de WhatsApp estritamente numérico para integração segura com wa.me."""
        if not self.whatsapp:
            return ''
        import re
        return re.sub(r'\D', '', self.whatsapp)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'business_info'
        verbose_name = "Informação do Negócio"
        verbose_name_plural = "Informação do Negócio"
        constraints = [
            CheckConstraint(check=Q(cancel_limit_hours__gte=0) & Q(cancel_limit_hours__lte=168), name='business_cancel_limit_range'),
        ]


class BusinessOpeningHours(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    business = models.ForeignKey(BusinessInfo, on_delete=models.CASCADE, related_name='opening_hours')
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name="Dia da Semana")
    is_open = models.BooleanField(default=True, verbose_name="Aberto?")
    opening_time = models.TimeField(default="09:00:00", verbose_name="Hora de Abertura")
    closing_time = models.TimeField(default="19:00:00", verbose_name="Hora de Fecho")
    lunch_start = models.TimeField(blank=True, null=True, verbose_name="Início Almoço")
    lunch_end = models.TimeField(blank=True, null=True, verbose_name="Fim Almoço")

    class Meta:
        db_table = 'business_opening_hours'
        ordering = ['weekday']
        unique_together = ('business', 'weekday')
        verbose_name = "Horário por Dia"
        verbose_name_plural = "Horários por Dia"
        constraints = [
            CheckConstraint(check=Q(weekday__gte=0) & Q(weekday__lte=6), name='opening_hours_weekday_valid'),
            CheckConstraint(check=Q(is_open=False) | Q(opening_time__lt=models.F('closing_time')), name='opening_hours_time_order'),
            CheckConstraint(
                check=(Q(lunch_start__isnull=True) & Q(lunch_end__isnull=True)) | 
                      (Q(lunch_start__isnull=False) & Q(lunch_end__isnull=False)),
                name='opening_hours_lunch_both_or_neither'
            ),
            CheckConstraint(
                check=Q(is_open=False) | Q(lunch_start__isnull=True) | (
                    Q(opening_time__lte=models.F('lunch_start')) &
                    Q(lunch_start__lt=models.F('lunch_end')) &
                    Q(lunch_end__lte=models.F('closing_time'))
                ),
                name='opening_hours_lunch_within_bounds'
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_open:
            if self.opening_time >= self.closing_time:
                raise ValidationError("A hora de abertura deve ser anterior à hora de fecho.")
            if (self.lunch_start and not self.lunch_end) or (self.lunch_end and not self.lunch_start):
                raise ValidationError("Ambos os horários de início e fim de almoço devem ser definidos juntos.")
            if self.lunch_start and self.lunch_end:
                if self.lunch_start >= self.lunch_end:
                    raise ValidationError("O início do almoço deve ser anterior ao fim do almoço.")
                if self.lunch_start < self.opening_time or self.lunch_end > self.closing_time:
                    raise ValidationError("O intervalo de almoço deve situar-se dentro do horário de abertura e fecho.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Aberto" if self.is_open else "Fechado"
        return f"{self.get_weekday_display()} ({status})"


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome da Categoria")
    order = models.IntegerField(default=0, verbose_name="Ordem")

    def __str__(self): return self.name
    class Meta:
        db_table = 'service_categories'
        ordering = ['order', 'name']
        verbose_name = "Categoria de Serviço"
        verbose_name_plural = "Categorias de Serviços"


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, verbose_name="Categoria")
    name = models.CharField(max_length=200, verbose_name="Nome do Serviço")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição")
    price = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Preço"
    )
    duration = models.IntegerField(
        default=30, 
        validators=[MinValueValidator(5), MaxValueValidator(480)],
        verbose_name="Duração (minutos)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo para novas marcações?")

    def clean(self):
        super().clean()
        if self.price is not None and self.price < Decimal('0.00'):
            raise ValidationError({'price': 'O preço não pode ser negativo.'})
        if self.duration is not None and self.duration <= 0:
            raise ValidationError({'duration': 'A duração tem de ser superior a 0 minutos.'})

    def __str__(self): 
        status = "" if self.is_active else " (Inativo)"
        return f"{self.name} - {self.price}€{status}"

    class Meta:
        db_table = 'services'
        ordering = ['category__order', 'name']
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"
        constraints = [
            CheckConstraint(check=Q(price__gte=0), name='service_price_non_negative'),
            CheckConstraint(check=Q(duration__gte=5) & Q(duration__lte=480), name='service_duration_valid'),
        ]


class StaffMember(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    role = models.CharField(max_length=100, verbose_name="Cargo")
    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL da Fotografia")
    is_active = models.BooleanField(default=True, verbose_name="Ativo para novas marcações?")

    def __str__(self): 
        status = "" if self.is_active else " (Inativo)"
        return f"{self.name} - {self.role}{status}"

    class Meta:
        db_table = 'staff_members'
        verbose_name = "Membro da Equipa"
        verbose_name_plural = "Equipa"


class Testimonial(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='testimonials', verbose_name="Utilizador")
    client_name = models.CharField(max_length=100, verbose_name="Nome do Cliente")
    text = models.TextField(verbose_name="Testemunho")
    rating = models.IntegerField(
        default=5, 
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Classificação (1 a 5)"
    )
    is_visible = models.BooleanField(default=False, verbose_name="Visível no Site (Moderado)")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Data de Submissão")

    def clean(self):
        super().clean()
        if self.rating is not None and (self.rating < 1 or self.rating > 5):
            raise ValidationError({'rating': 'A classificação deve situar-se entre 1 e 5 estrelas.'})
        if self.text and len(self.text.strip()) < 5:
            raise ValidationError({'text': 'O testemunho deve ter pelo menos 5 carateres.'})

    def __str__(self): return f"Review de {self.client_name} ({self.rating}★)"

    class Meta:
        db_table = 'testimonials'
        ordering = ['-created_at']
        verbose_name = "Testemunho"
        verbose_name_plural = "Testemunhos"
        constraints = [
            CheckConstraint(check=Q(rating__gte=1, rating__lte=5), name='testimonial_rating_range'),
        ]


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Pendente', 'Pendente'),
        ('Confirmada', 'Confirmada'),
        ('Aguardando Fecho', 'Aguardando Fecho'),
        ('Concluída', 'Concluída'),
        ('Faltou', 'Faltou (No-Show)'),
        ('Cancelada', 'Cancelada')
    ]

    VALID_TRANSITIONS = {
        'Pendente': {'Confirmada', 'Cancelada', 'Aguardando Fecho'},
        'Confirmada': {'Aguardando Fecho', 'Concluída', 'Faltou', 'Cancelada'},
        'Aguardando Fecho': {'Concluída', 'Faltou', 'Cancelada'},
        'Concluída': set(),
        'Faltou': set(),
        'Cancelada': set(),
    }

    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Cliente")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name="Serviço")
    staff_member = models.ForeignKey(StaffMember, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Especialista")
    date = models.DateField(verbose_name="Data da Marcação")
    time = models.TimeField(verbose_name="Hora da Marcação (Início)")
    end_time = models.TimeField(blank=True, null=True, verbose_name="Hora de Fim Estimada")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pendente')
    
    # Snapshots históricos da marcação
    service_name_at_booking = models.CharField(max_length=200, blank=True, null=True, verbose_name="Serviço (ao marcar)")
    price_at_booking = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="Preço (ao marcar)")
    duration_at_booking = models.IntegerField(blank=True, null=True, verbose_name="Duração em minutos (ao marcar)")
    
    cancellation_reason = models.CharField(max_length=100, blank=True, null=True, verbose_name="Motivo do Cancelamento")
    cancellation_notes = models.TextField(blank=True, null=True, verbose_name="Notas de Cancelamento")
    created_at = models.DateTimeField(auto_now_add=True)

    def transition_to(self, new_status, bypass=False):
        """Aplica a máquina de estados validando transições lógicas."""
        if not bypass and new_status != self.status:
            allowed = self.VALID_TRANSITIONS.get(self.status, set())
            if new_status not in allowed:
                raise ValidationError(f"Transição de estado inválida: de '{self.status}' para '{new_status}'.")
        self.status = new_status

    def clean(self):
        super().clean()
        if self.pk:
            old = Appointment.objects.filter(pk=self.pk).values('status').first()
            if old and old['status'] != self.status:
                allowed = self.VALID_TRANSITIONS.get(old['status'], set())
                if self.status not in allowed:
                    raise ValidationError({'status': f"Transição de estado inválida: de '{old['status']}' para '{self.status}'."})

    def save(self, *args, **kwargs):
        # Snapshots imutáveis ao momento da criação
        if self.service_id:
            if not self.service_name_at_booking:
                self.service_name_at_booking = self.service.name
            if self.price_at_booking is None:
                self.price_at_booking = self.service.price
            if self.duration_at_booking is None:
                self.duration_at_booking = self.service.duration

        effective_duration = self.duration_at_booking or (self.service.duration if self.service else 30)

        # Recalcular sempre o end_time se o time for fornecido para evitar end_time desatualizado
        if self.time:
            ref_date = self.date or date.today()
            dt = datetime.combine(ref_date, self.time) + timedelta(minutes=effective_duration)
            self.end_time = dt.time()

        super().save(*args, **kwargs)

    @property
    def effective_service_name(self):
        return self.service_name_at_booking or (self.service.name if self.service else "Serviço")

    @property
    def effective_price(self):
        return self.price_at_booking if self.price_at_booking is not None else (self.service.price if self.service else Decimal('0.00'))

    @property
    def effective_duration(self):
        return self.duration_at_booking or (self.service.duration if self.service else 30)

    @property
    def can_be_cancelled(self):
        if self.status not in ('Pendente', 'Confirmada'):
            return False
            
        business = BusinessInfo.objects.first()
        limit_hours = business.cancel_limit_hours if business else 24
        
        # Obter datetime da marcação (timezone aware)
        apt_dt = datetime.combine(self.date, self.time)
        current_tz = timezone.get_current_timezone()
        apt_aware = timezone.make_aware(apt_dt, current_tz) if timezone.is_naive(apt_dt) else apt_dt
        
        # Limite de tempo = agora + X horas
        return timezone.now() + timedelta(hours=limit_hours) <= apt_aware

    def __str__(self): 
        return f"{self.user.username} - {self.effective_service_name}"

    class Meta:
        db_table = 'appointments'
        ordering = ['-date', '-time']
        verbose_name = "Marcação"
        verbose_name_plural = "Marcações"
        indexes = [
            Index(fields=['date', 'staff_member', 'status'], name='idx_appt_date_staff_status'),
            Index(fields=['user', 'date'], name='idx_appt_user_date'),
        ]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, verbose_name="Telefone")
    terms_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Termos Aceites Em")
    privacy_policy_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Política de Privacidade Aceite Em")

    def __str__(self): return self.user.username
    class Meta:
        db_table = 'user_profiles'
        verbose_name = "Perfil de Utilizador"
