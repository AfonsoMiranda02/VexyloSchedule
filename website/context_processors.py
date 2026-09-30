from django.conf import settings
from .models import BusinessInfo

def business_processor(request):
    info = BusinessInfo.objects.first()
    if not info:
        info = BusinessInfo(
            name="VexyloSchedule",
            address="Morada a definir",
            phone="900000000",
            whatsapp="900000000",
            schedule="Horário a definir",
            cancel_limit_hours=24
        )
    return {
        'business_info': info,
        'google_oauth_enabled': getattr(settings, 'GOOGLE_OAUTH_ENABLED', False)
    }
