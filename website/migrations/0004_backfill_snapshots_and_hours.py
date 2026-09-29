# Generated manually for data preservation and snapshots backfill

from django.db import migrations

def backfill_data(apps, schema_editor):
    Appointment = apps.get_model('website', 'Appointment')
    BusinessInfo = apps.get_model('website', 'BusinessInfo')
    BusinessOpeningHours = apps.get_model('website', 'BusinessOpeningHours')

    # 1. Backfill snapshot fields for all existing appointments
    for apt in Appointment.objects.select_related('service').all():
        updated = False
        if apt.service:
            if not apt.service_name_at_booking:
                apt.service_name_at_booking = apt.service.name
                updated = True
            if apt.price_at_booking is None:
                apt.price_at_booking = apt.service.price
                updated = True
            if apt.duration_at_booking is None:
                apt.duration_at_booking = apt.service.duration
                updated = True
        if updated:
            apt.save(update_fields=['service_name_at_booking', 'price_at_booking', 'duration_at_booking'])

    # 2. Backfill BusinessOpeningHours for all existing BusinessInfo records
    for business in BusinessInfo.objects.all():
        for weekday in range(7):
            is_open = (weekday != 6) # Domingo fechado por omissão
            BusinessOpeningHours.objects.get_or_create(
                business=business,
                weekday=weekday,
                defaults={
                    'is_open': is_open,
                    'opening_time': business.opening_time or '09:00:00',
                    'closing_time': business.closing_time or '19:00:00',
                    'lunch_start': business.lunch_start,
                    'lunch_end': business.lunch_end,
                }
            )

def reverse_backfill(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('website', '0003_businessopeninghours_alter_testimonial_options_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_data, reverse_backfill),
    ]
