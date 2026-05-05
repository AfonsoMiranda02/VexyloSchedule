from django.contrib import admin
from .models import BusinessInfo, ServiceCategory, Service, Appointment, StaffMember, Testimonial

@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin): list_display = ('name', 'phone')

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin): list_display = ('name', 'order')

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin): list_display = ('name', 'category', 'price')

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin): list_display = ('name', 'role')

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin): list_display = ('client_name', 'rating')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'staff_member', 'date', 'time', 'status')
    list_filter = ('status', 'date', 'staff_member')
    search_fields = ('user__first_name', 'service__name')
