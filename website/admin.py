from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import BusinessInfo, ServiceCategory, Service, Appointment, StaffMember, Testimonial

class CustomUserAdmin(UserAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            # Create a new fieldsets tuple without 'user_permissions' and 'is_superuser'
            new_fieldsets = []
            for name, opts in fieldsets:
                if name == 'Permissions':
                    # Filter out 'user_permissions' and 'is_superuser'
                    fields = tuple(f for f in opts.get('fields', []) if f not in ('user_permissions', 'is_superuser'))
                    if fields:
                        new_fieldsets.append((name, {'fields': fields}))
                else:
                    new_fieldsets.append((name, opts))
            return tuple(new_fieldsets)
        return fieldsets

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin): 
    list_display = ('name', 'phone', 'email')

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin): 
    list_display = ('name', 'order')
    list_editable = ('order',)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin): 
    list_display = ('name', 'category', 'price')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin): 
    list_display = ('name', 'role')

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin): 
    list_display = ('client_name', 'rating')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    change_list_template = 'admin/website/appointment/change_list.html'
    
    list_display = ('user', 'service', 'staff_member', 'date', 'time', 'colored_status')
    list_filter = ('status', 'date', 'staff_member')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'service__name')
    actions = ['approve_appointments', 'cancel_appointments']
    date_hierarchy = 'date'

    def colored_status(self, obj):
        colors = {
            'Pendente': '#f59e0b',    # amber-500
            'Confirmada': '#10b981',  # emerald-500
            'Cancelada': '#ef4444'    # red-500
        }
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="color: white; background-color: {}; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px;">{}</span>', color, obj.status)
    colored_status.short_description = 'Estado'
    colored_status.admin_order_field = 'status'

    @admin.action(description='Confirmar Marcações Selecionadas')
    def approve_appointments(self, request, queryset):
        updated = queryset.update(status='Confirmada')
        self.message_user(request, f'{updated} marcação(ões) confirmada(s) com sucesso.')

    @admin.action(description='Cancelar Marcações Selecionadas')
    def cancel_appointments(self, request, queryset):
        updated = queryset.update(status='Cancelada')
        self.message_user(request, f'{updated} marcação(ões) cancelada(s) com sucesso.')

