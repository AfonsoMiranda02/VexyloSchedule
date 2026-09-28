from .models import BusinessInfo

def business_processor(request):
    info = BusinessInfo.objects.first()
    if not info:
        info = BusinessInfo(
            name="VexyloSchedule",
            address="Morada a definir",
            phone="900000000",
            whatsapp="900000000",
            schedule="Horário a definir"
        )
    return {
        'business_info': info
    }
