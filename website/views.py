from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from datetime import datetime, timedelta, time as dt_time
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import BusinessInfo, ServiceCategory, Appointment, StaffMember, Testimonial
from .forms import UserRegisterForm, AppointmentForm

def home_view(request):
    context = {
        'business_info': BusinessInfo.objects.first(),
        'categories': ServiceCategory.objects.prefetch_related('service_set').all(),
        'staff': StaffMember.objects.all(),
        'testimonials': Testimonial.objects.all(),
    }
    return render(request, 'website/home.html', context)

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            from .models import UserProfile
            UserProfile.objects.create(user=user, phone=form.cleaned_data.get('phone'))
            
            login(request, user)
            messages.success(request, "Conta criada com sucesso! Bem-vindo(a).")
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    return render(request, 'website/register.html', {'form': form})

@login_required
def book_appointment_view(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.user = request.user
            appointment.save()
            messages.success(request, "Marcação confirmada! O pagamento será efetuado presencialmente no salão.")
            return redirect('dashboard')
    else:
        form = AppointmentForm()
    return render(request, 'website/book_appointment.html', {'form': form})

@login_required
def client_dashboard_view(request):
    context = {
        'appointments': Appointment.objects.filter(user=request.user),
        'business_info': BusinessInfo.objects.first(),
    }
    return render(request, 'website/dashboard.html', context)

@login_required
def cancel_appointment_view(request, pk):
    appointment = get_object_or_404(Appointment, id=pk, user=request.user)
    if request.method == 'POST':
        if appointment.status != 'Cancelada':
            appointment.status = 'Cancelada'
            appointment.save()
            messages.success(request, "A sua marcação foi cancelada com sucesso.")
        else:
            messages.info(request, "Esta marcação já se encontra cancelada.")
    return redirect('dashboard')

def get_available_times(request):
    date_str = request.GET.get('date')
    staff_id = request.GET.get('staff_id')
    
    if not date_str:
        return JsonResponse({'available_times': []})
        
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'available_times': []})
        
    weekday = selected_date.weekday()
    
    # Dom (6) está fechado
    if weekday == 6:
        return JsonResponse({'available_times': []})
        
    # Segunda a Sábado: 09:00 - 19:00
    start_time = dt_time(9, 0)
    end_time = dt_time(19, 0)
        
    # Gerar blocos de 30 min
    available_blocks = []
    current_dt = datetime.combine(selected_date, start_time)
    end_dt = datetime.combine(selected_date, end_time)
    
    while current_dt + timedelta(minutes=30) <= end_dt:
        available_blocks.append(current_dt.time().strftime('%H:%M'))
        current_dt += timedelta(minutes=30)
        
    # Remover blocos ocupados
    appointments = Appointment.objects.filter(date=selected_date).exclude(status='Cancelada')
    
    if staff_id:
        appointments = appointments.filter(staff_member_id=staff_id)
        
    occupied_times = [apt.time.strftime('%H:%M') for apt in appointments]
    
    final_times = [t for t in available_blocks if t not in occupied_times]
    
    return JsonResponse({'available_times': final_times})

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model

@staff_member_required
def admin_dashboard_api_view(request):
    User = get_user_model()
    today = timezone.localdate()
    
    # KPIs
    total_clients = User.objects.filter(is_staff=False).count()
    appointments_today = Appointment.objects.filter(date=today).count()
    
    start_of_month = today.replace(day=1)
    # Revenue is sum of confirmed appointments price
    revenue_agg = Appointment.objects.filter(
        date__gte=start_of_month,
        status='Confirmada'
    ).aggregate(total=Sum('service__price'))
    revenue_month = revenue_agg['total'] or 0
    
    # Chart Data (Last 7 days)
    chart_labels = []
    chart_data = []
    
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from datetime import datetime, timedelta, time as dt_time
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import BusinessInfo, ServiceCategory, Appointment, StaffMember, Testimonial
from .forms import UserRegisterForm, AppointmentForm

def home_view(request):
    context = {
        'business_info': BusinessInfo.objects.first(),
        'categories': ServiceCategory.objects.prefetch_related('service_set').all(),
        'staff': StaffMember.objects.all(),
        'testimonials': Testimonial.objects.all(),
    }
    return render(request, 'website/home.html', context)

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            from .models import UserProfile
            UserProfile.objects.create(user=user, phone=form.cleaned_data.get('phone'))
            
            login(request, user)
            messages.success(request, "Conta criada com sucesso! Bem-vindo(a).")
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    return render(request, 'website/register.html', {'form': form})

@login_required
def book_appointment_view(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.user = request.user
            appointment.save()
            messages.success(request, "Marcação confirmada! O pagamento será efetuado presencialmente no salão.")
            return redirect('dashboard')
    else:
        form = AppointmentForm()
    return render(request, 'website/book_appointment.html', {'form': form})

@login_required
def client_dashboard_view(request):
    context = {
        'appointments': Appointment.objects.filter(user=request.user),
        'business_info': BusinessInfo.objects.first(),
    }
    return render(request, 'website/dashboard.html', context)

@login_required
def cancel_appointment_view(request, pk):
    appointment = get_object_or_404(Appointment, id=pk, user=request.user)
    if request.method == 'POST':
        if appointment.status != 'Cancelada':
            appointment.status = 'Cancelada'
            appointment.save()
            messages.success(request, "A sua marcação foi cancelada com sucesso.")
        else:
            messages.info(request, "Esta marcação já se encontra cancelada.")
    return redirect('dashboard')

def get_available_times(request):
    date_str = request.GET.get('date')
    staff_id = request.GET.get('staff_id')
    
    if not date_str:
        return JsonResponse({'available_times': []})
        
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'available_times': []})
        
    weekday = selected_date.weekday()
    
    # Dom (6) está fechado
    if weekday == 6:
        return JsonResponse({'available_times': []})
        
    # Segunda a Sábado: 09:00 - 19:00
    start_time = dt_time(9, 0)
    end_time = dt_time(19, 0)
        
    # Gerar blocos de 30 min
    available_blocks = []
    current_dt = datetime.combine(selected_date, start_time)
    end_dt = datetime.combine(selected_date, end_time)
    
    while current_dt + timedelta(minutes=30) <= end_dt:
        available_blocks.append(current_dt.time().strftime('%H:%M'))
        current_dt += timedelta(minutes=30)
        
    # Remover blocos ocupados
    appointments = Appointment.objects.filter(date=selected_date).exclude(status='Cancelada')
    
    if staff_id:
        appointments = appointments.filter(staff_member_id=staff_id)
        
    occupied_times = [apt.time.strftime('%H:%M') for apt in appointments]
    
    final_times = [t for t in available_blocks if t not in occupied_times]
    
    return JsonResponse({'available_times': final_times})

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model

@staff_member_required
def admin_dashboard_api_view(request):
    User = get_user_model()
    today = timezone.localdate()
    
    # KPIs
    total_clients = User.objects.filter(is_staff=False).count()
    appointments_today = Appointment.objects.filter(date=today).count()
    
    start_of_month = today.replace(day=1)
    # Revenue is sum of confirmed appointments price
    revenue_agg = Appointment.objects.filter(
        date__gte=start_of_month,
        status='Confirmada'
    ).aggregate(total=Sum('service__price'))
    revenue_month = revenue_agg['total'] or 0
    
    # Chart Data (Last 7 days)
    chart_labels = []
    chart_data = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Appointment.objects.filter(date=day).count()
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(count)
        
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = 1
    except Exception:
        db_status = 0
        
    return JsonResponse({
        'total_clients': total_clients,
        'appointments_today': appointments_today,
        'revenue_month': f"{revenue_month}€",
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'db_status': db_status
    })

@staff_member_required
def api_calendar_events(request):
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    # FullCalendar envia 'start' e 'end' no formato ISO8601
    appointments = Appointment.objects.all()
    
    if start_date:
        appointments = appointments.filter(date__gte=start_date.split('T')[0])
    if end_date:
        appointments = appointments.filter(date__lte=end_date.split('T')[0])
        
    events = []
    for appt in appointments:
        color = '#f59e0b'
        if appt.status == 'Confirmada':
            color = '#10b981'
        elif appt.status == 'Cancelada':
            color = '#ef4444'
            
        dt_str = f"{appt.date.isoformat()}T{appt.time.isoformat()}"
        events.append({
            'id': appt.id,
            'title': f'{appt.service.name} - {appt.user.first_name or appt.user.username}',
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
        
    return JsonResponse(events, safe=False)

from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def submit_testimonial(request):
    try:
        data = json.loads(request.body)
        rating = int(data.get('rating', 5))
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse({'success': False, 'error': 'O texto do testemunho é obrigatório.'})
            
        if rating < 1 or rating > 5:
            return JsonResponse({'success': False, 'error': 'A classificação deve ser entre 1 e 5.'})
            
        client_name = request.user.first_name or request.user.username
        
        Testimonial.objects.create(
            client_name=client_name,
            text=text,
            rating=rating
        )
        
        return JsonResponse({'success': True, 'message': 'Obrigado pelo seu testemunho!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def privacy_policy_view(request):
    return render(request, 'website/privacy_policy.html', {'business_info': BusinessInfo.objects.first()})

def terms_conditions_view(request):
    return render(request, 'website/terms_conditions.html', {'business_info': BusinessInfo.objects.first()})
