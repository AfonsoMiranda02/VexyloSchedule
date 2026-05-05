from .models import BusinessInfo

def business_processor(request):
    return {
        'business_info': BusinessInfo.objects.first()
    }
