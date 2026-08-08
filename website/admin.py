from django.contrib import admin
from django.utils.html import format_html
from .models import BusinessInfo, ServiceCategory, Service, Appointment, StaffMember, Testimonial

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

    def changelist_view(self, request, extra_context=None):
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        
        response = super().changelist_view(request, extra_context)
        
        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response
            
        events = []
        for appt in qs:
            color = '#f59e0b'
            if appt.status == 'Confirmada':
                color = '#10b981'
            elif appt.status == 'Cancelada':
                color = '#ef4444'
                
            dt_str = f"{appt.date.isoformat()}T{appt.time.isoformat()}"
            
            events.append({
                'title': f'{appt.service.name} - {appt.user.username}',
                'start': dt_str,
                'url': f'/vexylo-admin/website/appointment/{appt.id}/change/',
                'backgroundColor': color,
                'borderColor': color,
                'extendedProps': {
                    'client_name': appt.user.first_name or appt.user.username,
                    'service_name': appt.service.name,
                    'time': appt.time.strftime('%H:%M'),
                    'status': appt.status,
                    'price': str(appt.service.price)
                }
            })
            
        response.context_data['calendar_events'] = json.dumps(events, cls=DjangoJSONEncoder)
        return response
