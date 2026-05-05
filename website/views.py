from django.shortcuts import render, redirect
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
    
    # Qua (2) e Dom (6) está fechado
    if weekday == 2 or weekday == 6:
        return JsonResponse({'available_times': []})
        
    # Horários padrão
    if weekday == 5: # Sábado: 08:30 - 18:00
        start_time = dt_time(8, 30)
        end_time = dt_time(18, 0)
    else: # Seg, Ter, Qui, Sex: 09:30 - 19:00
        start_time = dt_time(9, 30)
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

def privacy_policy_view(request):
    return render(request, 'website/privacy_policy.html', {'business_info': BusinessInfo.objects.first()})

def terms_conditions_view(request):
    return render(request, 'website/terms_conditions.html', {'business_info': BusinessInfo.objects.first()})
