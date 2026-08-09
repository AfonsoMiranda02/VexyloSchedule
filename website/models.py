from django.db import models
from django.contrib.auth.models import User

class BusinessInfo(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nome da Empresa")
    address = models.CharField(max_length=255, verbose_name="Morada")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    phone = models.CharField(max_length=50, verbose_name="Telefone")
    whatsapp = models.CharField(max_length=50, blank=True, null=True, verbose_name="WhatsApp")
    nif = models.CharField(max_length=20, null=True, blank=True, verbose_name="NIF")
    schedule = models.TextField(verbose_name="Horário de Funcionamento")
    google_maps_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link do Google Maps")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição da Empresa")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Informação do Negócio"
        verbose_name_plural = "Informação do Negócio"

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome da Categoria")
    order = models.IntegerField(default=0, verbose_name="Ordem")

    def __str__(self): return self.name
    class Meta: 
        ordering = ['order', 'name']
        verbose_name = "Categoria de Serviço"
        verbose_name_plural = "Categorias de Serviços"

class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, verbose_name="Categoria")
    name = models.CharField(max_length=200, verbose_name="Nome do Serviço")
    description = models.TextField(blank=True, null=True, verbose_name="Descrição")
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Preço")

    def __str__(self): return f"{self.name} - {self.price}€"
    class Meta: 
        ordering = ['category__order', 'name']
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

class StaffMember(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    role = models.CharField(max_length=100, verbose_name="Cargo")
    avatar_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL da Fotografia")

    def __str__(self): return f"{self.name} - {self.role}"
    class Meta:
        verbose_name = "Membro da Equipa"
        verbose_name_plural = "Equipa"

class Testimonial(models.Model):
    client_name = models.CharField(max_length=100, verbose_name="Nome do Cliente")
    text = models.TextField(verbose_name="Testemunho")
    rating = models.IntegerField(default=5, verbose_name="Classificação (1 a 5)")

    def __str__(self): return f"Review de {self.client_name}"
    class Meta: 
        verbose_name = "Testemunho"
        verbose_name_plural = "Testemunhos"

class Appointment(models.Model):
    STATUS_CHOICES = [('Pendente', 'Pendente'), ('Confirmada', 'Confirmada'), ('Cancelada', 'Cancelada')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Cliente")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name="Serviço")
    staff_member = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Especialista (Opcional)")
    date = models.DateField(verbose_name="Data da Marcação")
    time = models.TimeField(verbose_name="Hora da Marcação")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pendente')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.user.username} - {self.service.name}"
    class Meta: 
        ordering = ['-date', '-time']
        verbose_name = "Marcação"
        verbose_name_plural = "Marcações"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, verbose_name="Telefone")

    def __str__(self): return self.user.username
    class Meta: verbose_name = "Perfil de Utilizador"
