from django.db import models
from django.contrib.auth.models import User
from datetime import time

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
    
    # Horários estruturados para cálculo de disponibilidade
    opening_time = models.TimeField(default=time(9, 0), verbose_name="Hora de Abertura")
    closing_time = models.TimeField(default=time(19, 0), verbose_name="Hora de Fecho")
    lunch_start = models.TimeField(blank=True, null=True, verbose_name="Início Almoço")
    lunch_end = models.TimeField(blank=True, null=True, verbose_name="Fim Almoço")
    
    google_maps_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link do Google Maps")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição da Empresa")
    cancel_limit_hours = models.IntegerField(default=24, verbose_name="Horas limite para cancelamento (Ex: 24 para 24h antes)")

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'business_info'
        verbose_name = "Informação do Negócio"
        verbose_name_plural = "Informação do Negócio"

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
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, verbose_name="Categoria")
    name = models.CharField(max_length=200, verbose_name="Nome do Serviço")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição")
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Preço")
    duration = models.IntegerField(default=30, verbose_name="Duração (minutos)")

    def __str__(self): return f"{self.name} - {self.price}€"
    class Meta:
        db_table = 'services'
        ordering = ['category__order', 'name']
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

class StaffMember(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    role = models.CharField(max_length=100, verbose_name="Cargo")
    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL da Fotografia")

    def __str__(self): return f"{self.name} - {self.role}"
    class Meta:
        db_table = 'staff_members'
        verbose_name = "Membro da Equipa"
        verbose_name_plural = "Equipa"

class Testimonial(models.Model):
    client_name = models.CharField(max_length=100, verbose_name="Nome do Cliente")
    text = models.TextField(verbose_name="Testemunho")
    rating = models.IntegerField(default=5, verbose_name="Classificação (1 a 5)")
    is_visible = models.BooleanField(default=True, verbose_name="Visível no Site")

    def __str__(self): return f"Review de {self.client_name}"
    class Meta:
        db_table = 'testimonials'
        verbose_name = "Testemunho"
        verbose_name_plural = "Testemunhos"

class Appointment(models.Model):
    STATUS_CHOICES = [('Pendente', 'Pendente'), ('Confirmada', 'Confirmada'), ('Cancelada', 'Cancelada')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Cliente")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name="Serviço")
    staff_member = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Especialista (Opcional)")
    date = models.DateField(verbose_name="Data da Marcação")
    time = models.TimeField(verbose_name="Hora da Marcação (Início)")
    end_time = models.TimeField(blank=True, null=True, verbose_name="Hora de Fim Estimada")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pendente')
    cancellation_reason = models.CharField(max_length=100, blank=True, null=True, verbose_name="Motivo do Cancelamento")
    cancellation_notes = models.TextField(blank=True, null=True, verbose_name="Notas de Cancelamento")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.time and self.service and not self.end_time:
            import datetime
            dt = datetime.datetime.combine(datetime.date.today(), self.time)
            dt = dt + datetime.timedelta(minutes=self.service.duration)
            self.end_time = dt.time()
        super().save(*args, **kwargs)

    @property
    def can_be_cancelled(self):
        from django.utils import timezone
        import datetime
        business = BusinessInfo.objects.first()
        limit_hours = business.cancel_limit_hours if business else 24
        
        # Obter datetime da marcação (timezone aware)
        apt_dt = datetime.datetime.combine(self.date, self.time)
        apt_aware = timezone.make_aware(apt_dt)
        
        # Limite de tempo = agora + X horas
        return timezone.now() + datetime.timedelta(hours=limit_hours) <= apt_aware

    def __str__(self): return f"{self.user.username} - {self.service.name}"
    class Meta:
        db_table = 'appointments'
        ordering = ['-date', '-time']
        verbose_name = "Marcação"
        verbose_name_plural = "Marcações"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, verbose_name="Telefone")

    def __str__(self): return self.user.username
    class Meta:
        db_table = 'user_profiles'
        verbose_name = "Perfil de Utilizador"
