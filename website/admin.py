from django.contrib import admin, messages
from django.utils.html import format_html
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from .models import (
    BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, 
    Appointment, StaffMember, Testimonial, UserProfile, Utilizador
)
from .forms import AppointmentAdminForm

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil'
    fk_name = 'user'
    readonly_fields = ('terms_accepted_at', 'privacy_policy_accepted_at')

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_phone', 'is_staff')

    def get_phone(self, instance):
        if hasattr(instance, 'profile'):
            return instance.profile.phone
        return ''
    get_phone.short_description = 'Telefone'

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            new_fieldsets = []
            for name, opts in fieldsets:
                if name == 'Permissions':
                    fields = tuple(f for f in opts.get('fields', []) if f not in ('user_permissions', 'is_superuser'))
                    if fields:
                        new_fieldsets.append((name, {'fields': fields}))
                else:
                    new_fieldsets.append((name, opts))
            return tuple(new_fieldsets)
        return fieldsets

    def delete_model(self, request, obj):
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            self.message_user(
                request,
                f"Não é possível eliminar '{obj}' porque existem marcações históricas associadas. "
                "Para desativar o acesso sem perder o histórico, desmarque a opção 'Ativo' (is_active=False).",
                level=messages.ERROR
            )

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            self.message_user(
                request,
                "Um ou mais clientes não puderam ser eliminados porque possuem marcações históricas associadas. "
                "Recomenda-se desativá-los (is_active=False) para preservar o histórico.",
                level=messages.ERROR
            )

admin.site.unregister(User)
admin.site.register(Utilizador, CustomUserAdmin)


class BusinessOpeningHoursInline(admin.TabularInline):
    model = BusinessOpeningHours
    extra = 0
    can_delete = False
    fields = ('weekday', 'is_open', 'opening_time', 'closing_time', 'lunch_start', 'lunch_end')
    readonly_fields = ('weekday',)

    def has_add_permission(self, request, obj=None):
        # Permite no máximo 7 dias (0 a 6)
        if obj and obj.opening_hours.count() >= 7:
            return False
        return True


@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin): 
    list_display = ('name', 'phone', 'email', 'cancel_limit_hours')
    inlines = [BusinessOpeningHoursInline]

    def has_add_permission(self, request):
        # Singleton: se já existe um registo, não permite criar outro via admin
        if BusinessInfo.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Previne apagar as configurações essenciais do negócio
        return False


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin): 
    list_display = ('name', 'order')
    list_editable = ('order',)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin): 
    list_display = ('name', 'category', 'price', 'duration', 'is_active')
    list_filter = ('category', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)

    def delete_model(self, request, obj):
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            self.message_user(
                request,
                f"Não é possível eliminar o serviço '{obj.name}' porque existem marcações associadas. "
                "Para o retirar do catálogo público, desative o serviço (is_active=False).",
                level=messages.ERROR
            )

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            self.message_user(
                request,
                "Alguns serviços não puderam ser eliminados porque possuem histórico de marcações. "
                "Recomenda-se desativá-los (is_active=False).",
                level=messages.ERROR
            )


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin): 
    list_display = ('name', 'role', 'is_active')
    list_filter = ('is_active',)
    list_editable = ('is_active',)

    def delete_model(self, request, obj):
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            self.message_user(
                request,
                f"Não é possível eliminar o profissional '{obj.name}' porque existem marcações associadas. "
                "Para o inativar sem perder o histórico, desmarque a opção 'Ativo' (is_active=False).",
                level=messages.ERROR
            )

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            self.message_user(
                request,
                "Alguns profissionais não puderam ser eliminados porque possuem marcações no seu histórico. "
                "Recomenda-se desativá-los (is_active=False).",
                level=messages.ERROR
            )


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin): 
    list_display = ('client_name', 'rating', 'is_visible', 'user', 'created_at')
    list_editable = ('is_visible',)
    list_filter = ('is_visible', 'rating', 'created_at')
    readonly_fields = ('client_name', 'user', 'text', 'rating', 'created_at')
    actions = ['approve_testimonials', 'hide_testimonials']

    @admin.action(description='Aprovar Testemunhos Selecionados (Visíveis)')
    def approve_testimonials(self, request, queryset):
        count = queryset.update(is_visible=True)
        self.message_user(request, f"{count} testemunho(s) aprovado(s) e visíveis no site.")

    @admin.action(description='Ocultar Testemunhos Selecionados')
    def hide_testimonials(self, request, queryset):
        count = queryset.update(is_visible=False)
        self.message_user(request, f"{count} testemunho(s) ocultado(s).")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    form = AppointmentAdminForm
    change_list_template = 'admin/website/appointment/change_list.html'
    
    list_display = ('user', 'get_service_name', 'staff_member', 'date', 'time', 'end_time', 'get_price', 'colored_status')
    list_filter = ('status', 'date', 'staff_member')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'service_name_at_booking', 'service__name')
    actions = ['approve_appointments', 'await_closure_appointments', 'complete_appointments', 'no_show_appointments', 'cancel_appointments']
    date_hierarchy = 'date'
    readonly_fields = ('service_name_at_booking', 'price_at_booking', 'duration_at_booking', 'created_at')

    def save_model(self, request, obj, form, change):
        from website.services.booking import BookingService, BookingError
        try:
            BookingService.save_admin_appointment(obj)
        except (BookingError, ValidationError) as e:
            self.message_user(request, f"Erro ao processar marcação: {e}", level=messages.ERROR)
            raise

    def get_service_name(self, obj):
        return obj.effective_service_name
    get_service_name.short_description = 'Serviço'

    def get_price(self, obj):
        return f"{obj.effective_price}€"
    get_price.short_description = 'Preço'

    def colored_status(self, obj):
        colors = {
            'Pendente': '#f59e0b',          # amber-500
            'Confirmada': '#10b981',        # emerald-500
            'Aguardando Fecho': '#8b5cf6',  # purple-500
            'Concluída': '#3b82f6',         # blue-500
            'Faltou': '#6b7280',            # gray-500
            'Cancelada': '#ef4444'          # red-500
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 4px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;">{}</span>',
            color, obj.status
        )
    colored_status.short_description = 'Estado'
    colored_status.admin_order_field = 'status'

    @admin.action(description='Confirmar Marcações (Pendente -> Confirmada)')
    def approve_appointments(self, request, queryset):
        success = 0
        for apt in queryset:
            try:
                apt.transition_to('Confirmada', bypass=request.user.is_superuser)
                apt.save()
                success += 1
            except ValidationError as e:
                self.message_user(request, f"Marcação #{apt.id}: {e}", level='ERROR')
        self.message_user(request, f'{success} marcação(ões) confirmada(s) com sucesso.')

    @admin.action(description='Aguardar Fecho (Confirmada -> Aguardando Fecho)')
    def await_closure_appointments(self, request, queryset):
        success = 0
        for apt in queryset:
            try:
                apt.transition_to('Aguardando Fecho', bypass=request.user.is_superuser)
                apt.save()
                success += 1
            except ValidationError as e:
                self.message_user(request, f"Marcação #{apt.id}: {e}", level='ERROR')
        self.message_user(request, f'{success} marcação(ões) movida(s) para Aguardando Fecho.')

    @admin.action(description='Marcar como Concluída (Aguardando Fecho / Confirmada -> Concluída)')
    def complete_appointments(self, request, queryset):
        success = 0
        for apt in queryset:
            try:
                apt.transition_to('Concluída', bypass=request.user.is_superuser)
                apt.save()
                success += 1
            except ValidationError as e:
                self.message_user(request, f"Marcação #{apt.id}: {e}", level='ERROR')
        self.message_user(request, f'{success} marcação(ões) marcada(s) como Concluída.')

    @admin.action(description='Marcar como Faltou / No-Show')
    def no_show_appointments(self, request, queryset):
        success = 0
        for apt in queryset:
            try:
                apt.transition_to('Faltou', bypass=request.user.is_superuser)
                apt.save()
                success += 1
            except ValidationError as e:
                self.message_user(request, f"Marcação #{apt.id}: {e}", level='ERROR')
        self.message_user(request, f'{success} marcação(ões) marcada(s) como Faltou (No-Show).')

    @admin.action(description='Cancelar Marcações')
    def cancel_appointments(self, request, queryset):
        success = 0
        for apt in queryset:
            try:
                apt.transition_to('Cancelada', bypass=request.user.is_superuser)
                apt.save()
                success += 1
            except ValidationError as e:
                self.message_user(request, f"Marcação #{apt.id}: {e}", level='ERROR')
        self.message_user(request, f'{success} marcação(ões) cancelada(s) com sucesso.')
