import json
import logging
from datetime import datetime, date, timedelta, time as dt_time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q, Prefetch
from django.conf import settings
from django.urls import reverse
from django.contrib.auth import views as auth_views

from .models import (
    BusinessInfo, BusinessOpeningHours, ServiceCategory, Service, 
    Appointment, StaffMember, Testimonial, UserProfile
)
from .forms import UserRegisterForm, AppointmentForm, CompleteProfileForm
from .services.booking import (
    BookingService, BookingError, BusinessClosedError, 
    InvalidSlotError, SlotOccupiedError, StaffUnavailableError
)
from .utils.ratelimit import rate_limit

logger = logging.getLogger(__name__)


def home_view(request):
    """Página inicial pública do VexyloSchedule com serviços e categorias ativas."""
    active_services_prefetch = Prefetch(
        'service_set',
        queryset=Service.objects.filter(is_active=True).order_by('name')
    )
    categories = (
        ServiceCategory.objects
        .prefetch_related(active_services_prefetch)
        .filter(service__is_active=True)
        .distinct()
        .order_by('order', 'name')
    )
    context = {
        'business_info': BusinessInfo.get_solo(),
        'categories': categories,
        'staff': StaffMember.objects.filter(is_active=True),
        'testimonials': Testimonial.objects.filter(is_visible=True),
    }
    return render(request, 'website/home.html', context)


@method_decorator(rate_limit('login', limit=5, period=300), name='dispatch')
class CustomLoginView(auth_views.LoginView):
    """Login com rate limiting por IP/conta para mitigar ataques de força bruta."""
    template_name = 'registration/login.html'


@rate_limit('register', limit=5, period=300)
def register_view(request):
    """Registo de novos clientes com validação de termos e normalização de email."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            from django.db import IntegrityError
            try:
                user = form.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, "Conta criada com sucesso! Bem-vindo(a).")
                return redirect('dashboard')
            except IntegrityError as exc:
                err_msg = str(exc).lower()
                if 'unique' in err_msg or 'email' in err_msg or 'username' in err_msg:
                    logger.warning("Concorrência de registo detetada para email/username duplicado: %s", exc)
                    form.add_error('email', "Este email já está registado.")
                else:
                    raise
    else:
        form = UserRegisterForm()
    return render(request, 'website/register.html', {'form': form})


@login_required
def complete_profile_view(request):
    """
    Página de aceitação explícita de Termos e Política de Privacidade
    para utilizadores que entram via Google OAuth / Social Login.
    Preserva destinos de redirecionamento seguros (parâmetro 'next').
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    from django.utils.http import url_has_allowed_host_and_scheme
    raw_next = request.POST.get('next') or request.GET.get('next')
    if raw_next and url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target_next = raw_next
    else:
        target_next = reverse('dashboard')

    if profile.terms_accepted_at and profile.privacy_policy_accepted_at:
        return redirect(target_next)
        
    if request.method == 'POST':
        form = CompleteProfileForm(request.POST)
        if form.is_valid():
            now = timezone.now()
            profile.phone = form.cleaned_data['phone']
            profile.terms_accepted_at = now
            profile.privacy_policy_accepted_at = now
            profile.save()
            messages.success(request, "Registo completado com sucesso! Bem-vindo(a) ao VexyloSchedule.")
            return redirect(target_next)
    else:
        form = CompleteProfileForm(initial={'phone': profile.phone or ''})
        
    return render(request, 'website/complete_profile.html', {
        'form': form,
        'next': target_next if target_next != reverse('dashboard') else '',
        'business_info': BusinessInfo.get_solo()
    })


@login_required
@rate_limit('book', limit=15, period=60)
def book_appointment_view(request):
    """
    Agendamento de marcações server-authoritative através do BookingService.
    Nunca confia nas opções enviadas pelo browser e impede double-booking concorrente.
    """
    business = BusinessInfo.get_solo()
    if business and business.pk:
        closed_days_qs = BusinessOpeningHours.objects.filter(business=business, is_open=False)
        closed_weekdays_js = [(day.weekday + 1) % 7 for day in closed_days_qs]
    else:
        closed_weekdays_js = []

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            service = form.cleaned_data['service']
            staff_member = form.cleaned_data.get('staff_member')
            target_date = form.cleaned_data['date']
            target_time = form.cleaned_data['time']

            try:
                # O BookingService executa a reserva dentro de transaction.atomic com locks
                appointment = BookingService.book_appointment(
                    user=request.user,
                    service=service,
                    target_date=target_date,
                    start_time=target_time,
                    staff_member=staff_member
                )
                messages.success(request, "Marcação confirmada! O pagamento será efetuado presencialmente no salão.")
                return redirect('dashboard')
            except BookingError as e:
                messages.error(request, str(e))
            except Exception:
                logger.exception("Erro inesperado ao criar marcação")
                messages.error(request, "Ocorreu um erro ao processar a marcação. Por favor verifique os dados e tente novamente.")
    else:
        form = AppointmentForm()
        
    return render(request, 'website/book_appointment.html', {
        'form': form,
        'closed_weekdays_js': closed_weekdays_js,
        'business_info': business
    })


@login_required
def client_dashboard_view(request):
    """Área pessoal do cliente com histórico de marcações e estados fidedignos."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST' and 'phone' in request.POST:
        phone_val = request.POST.get('phone', '').strip()
        if phone_val:
            profile.phone = phone_val
            profile.save()
            messages.success(request, 'Número de telefone atualizado com sucesso!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Por favor insira um número de telefone válido.')

    prompt_phone = not bool(profile.phone)
    appointments = (
        Appointment.objects.filter(user=request.user)
        .select_related('service', 'staff_member')
        .order_by('-date', '-time')
    )

    context = {
        'appointments': appointments,
        'business_info': BusinessInfo.get_solo(),
        'prompt_phone': prompt_phone,
    }
    return render(request, 'website/dashboard.html', context)


@login_required
@require_POST
@rate_limit('cancel', limit=10, period=60)
def cancel_appointment_view(request, pk):
    """
    Cancelamento seguro de marcações verificado server-side.
    Valida propriedade, elegibilidade de estado e limite de antecedência configurado.
    """
    appointment = get_object_or_404(Appointment, id=pk, user=request.user)
    
    if not appointment.can_be_cancelled:
        business = BusinessInfo.get_solo()
        messages.error(
            request, 
            f"Já não é possível cancelar esta marcação online (o prazo limite é de {business.cancel_limit_hours} horas antes do horário)."
        )
        return redirect('dashboard')
        
    ALLOWED_CANCEL_REASONS = {
        'Mudança de planos',
        'Imprevisto',
        'Insatisfação',
        'Outro'
    }
    raw_reason = request.POST.get('cancellation_reason', '').strip()
    reason = raw_reason if raw_reason in ALLOWED_CANCEL_REASONS else 'Outro'
    notes = request.POST.get('cancellation_notes', '').strip()[:500]
    
    try:
        appointment.transition_to('Cancelada')
        appointment.cancellation_reason = reason
        appointment.cancellation_notes = notes
        appointment.save()
        messages.success(request, "A sua marcação foi cancelada com sucesso.")
    except Exception:
        logger.exception(f"Erro ao cancelar marcação #{pk}")
        messages.error(request, "Não foi possível cancelar a marcação. Por favor contacte o suporte.")
        
    return redirect('dashboard')


def get_available_times(request):
    """
    API de consulta de disponibilidade reutilizando BookingService.
    Valida parâmetros de entrada estritamente, retornando HTTP 400 em caso de inputs inválidos.
    """
    date_str = request.GET.get('date')
    staff_id = request.GET.get('staff_id')
    service_id = request.GET.get('service_id')
    
    if not date_str or not service_id:
        return JsonResponse({'error': 'Parâmetros date e service_id são obrigatórios.'}, status=400)
        
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Formato de data inválido. Utilize o formato AAAA-MM-DD.'}, status=400)

    try:
        service = Service.objects.get(id=service_id, is_active=True)
    except (Service.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Serviço inexistente ou inativo.'}, status=400)
        
    staff_member = None
    if staff_id:
        try:
            staff_member = StaffMember.objects.get(id=staff_id, is_active=True)
        except (StaffMember.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Profissional especificado não existe ou encontra-se inativo.'}, status=400)

    slots = BookingService.get_available_slots(
        target_date=selected_date,
        service=service,
        staff_member=staff_member
    )
    
    return JsonResponse({'available_times': slots})


@staff_member_required
def admin_dashboard_api_view(request):
    """
    Métricas e KPIs analíticos do painel de administração.
    IMPORTANTE: Estritamente livre de mutações de base de dados (GET idempotente).
    """
    User = get_user_model()
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    # KPIs sem efeitos secundários
    total_clients = User.objects.filter(is_staff=False).count()
    appointments_today = Appointment.objects.filter(date=today).exclude(status='Cancelada').count()
    upcoming_appointments = Appointment.objects.filter(
        date__gte=today, 
        status__in=['Pendente', 'Confirmada']
    ).count()
    total_services = Service.objects.filter(is_active=True).count()

    # Gráfico dos últimos 7 dias
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Appointment.objects.filter(date=day).exclude(status='Cancelada').count()
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(count)

    # Top Serviços com base no nome gravado no momento da marcação (snapshots históricos)
    top_services_qs = (
        Appointment.objects.exclude(status='Cancelada')
        .values('service_name_at_booking', 'service__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    top_services_labels = [
        item['service_name_at_booking'] or item['service__name'] or 'Serviço' 
        for item in top_services_qs
    ]
    top_services_data = [item['total'] for item in top_services_qs]

    # Distribuição de estados
    status_qs = Appointment.objects.values('status').annotate(total=Count('id')).order_by('-total')
    status_labels = [item['status'] for item in status_qs]
    status_data = [item['total'] for item in status_qs]

    # Próxima Marcação Ativa
    next_appointment_obj = Appointment.objects.filter(
        Q(date=today, time__gte=now_time) | Q(date__gt=today),
        status__in=['Pendente', 'Confirmada']
    ).select_related('user', 'service', 'staff_member').order_by('date', 'time').first()

    next_appt_data = None
    if next_appointment_obj:
        client_display = (
            next_appointment_obj.user.get_full_name() or 
            next_appointment_obj.user.username
        )
        next_appt_data = {
            'client_name': client_display,
            'service_name': next_appointment_obj.effective_service_name,
            'staff_name': next_appointment_obj.staff_member.name if next_appointment_obj.staff_member else 'Qualquer profissional',
            'date': next_appointment_obj.date.strftime('%d/%m/%Y'),
            'time': next_appointment_obj.time.strftime('%H:%M'),
        }

    return JsonResponse({
        'total_clients': total_clients,
        'appointments_today': appointments_today,
        'upcoming_appointments': upcoming_appointments,
        'total_services': total_services,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'top_services_labels': top_services_labels,
        'top_services_data': top_services_data,
        'status_labels': status_labels,
        'status_data': status_data,
        'next_appointment': next_appt_data,
    })


@staff_member_required
def api_calendar_events(request):
    """
    Retorna os eventos de calendário em formato compatível com FullCalendar.
    Valida inputs de datas ISO, respeita intervalo exclusivo de fim e usa reverse para URLs.
    """
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    search_query = request.GET.get('q', '').strip()
    
    appointments = Appointment.objects.select_related('user', 'service', 'staff_member').all()
    
    if start_date:
        try:
            start_clean = start_date.split('T')[0]
            start_val = datetime.strptime(start_clean, '%Y-%m-%d').date()
            appointments = appointments.filter(date__gte=start_val)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Parâmetro start inválido.'}, status=400)

    if end_date:
        try:
            end_clean = end_date.split('T')[0]
            end_val = datetime.strptime(end_clean, '%Y-%m-%d').date()
            # FullCalendar end é exclusivo: data estritamente menor que end_val
            appointments = appointments.filter(date__lt=end_val)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Parâmetro end inválido.'}, status=400)
        
    if search_query:
        appointments = appointments.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
        
    events = []
    colors = {
        'Confirmada': '#10b981',
        'Pendente': '#f59e0b',
        'Aguardando Fecho': '#8b5cf6',
        'Concluída': '#3b82f6',
        'Cancelada': '#ef4444',
        'Faltou': '#6b7280'
    }

    for appt in appointments:
        color = colors.get(appt.status, '#6b7280')
        client_name = appt.user.get_full_name() or appt.user.username
            
        dt_str = f"{appt.date.isoformat()}T{appt.time.isoformat()}"
        end_time = appt.end_time or (datetime.combine(appt.date, appt.time) + timedelta(minutes=appt.effective_duration)).time()
        
        event_dict = {
            'id': appt.id,
            'title': f"{appt.effective_service_name} - {client_name}",
            'start': dt_str,
            'end': f"{appt.date.isoformat()}T{end_time.isoformat()}",
            'url': reverse('admin:website_appointment_change', args=[appt.id]),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'client_name': client_name,
                'service_name': appt.effective_service_name,
                'time': appt.time.strftime('%H:%M'),
                'status': appt.status,
                'price': str(appt.effective_price)
            }
        }
        events.append(event_dict)
        
    return JsonResponse(events, safe=False)


@login_required
@require_POST
@rate_limit('testimonial', limit=3, period=3600)
def submit_testimonial(request):
    """
    Submissão de testemunhos protegida com moderação obrigatória (is_visible=False)
    e vinculação ao utilizador autenticado.
    """
    try:
        data = json.loads(request.body)
        rating = int(data.get('rating', 5))
        text = data.get('text', '').strip()
        
        if not text or len(text) < 5:
            return JsonResponse({'success': False, 'error': 'O texto do testemunho deve ter pelo menos 5 carateres.'}, status=400)
            
        if len(text) > 1000:
            return JsonResponse({'success': False, 'error': 'O texto não pode exceder 1000 carateres.'}, status=400)

        if rating < 1 or rating > 5:
            return JsonResponse({'success': False, 'error': 'A classificação deve ser entre 1 e 5 estrelas.'}, status=400)
            
        client_name = request.user.first_name or request.user.username
        
        Testimonial.objects.create(
            user=request.user,
            client_name=client_name,
            text=text,
            rating=rating,
            is_visible=False # Moderação obrigatória por omissão
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'Obrigado pelo seu testemunho! O seu comentário será revisto pela nossa equipa antes de ser publicado.'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Formato de dados JSON inválido.'}, status=400)
    except Exception:
        logger.exception("Erro inesperado ao submeter testemunho")
        return JsonResponse({
            'success': False, 
            'error': 'Ocorreu um erro interno ao processar a avaliação. Por favor tente novamente mais tarde.'
        }, status=500)


def privacy_policy_view(request):
    return render(request, 'website/privacy_policy.html', {'business_info': BusinessInfo.get_solo()})


def terms_conditions_view(request):
    return render(request, 'website/terms_conditions.html', {'business_info': BusinessInfo.get_solo()})


@method_decorator(rate_limit('password_reset', limit=3, period=900), name='dispatch')
class CustomPasswordResetView(auth_views.PasswordResetView):
    """
    Recuperação de password segura contra envenenamento de cabeçalho Host e abusos de spam.
    Garante o envio de exatamente UM email através da chamada direta a form.save
    sem invocar super().form_valid(form) duplicado.
    Preserva a porta para desenvolvimento local (ex: localhost:8000) e falha de forma
    segura caso o serviço de email esteja indisponível.
    """
    def dispatch(self, request, *args, **kwargs):
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        if backend.endswith('dummy.EmailBackend'):
            from django.http import HttpResponseServerError
            return HttpResponseServerError("O envio de emails está desativado nesta configuração.")
        return super().dispatch(request, *args, **kwargs)

    def get_trusted_domain_and_protocol(self):
        from urllib.parse import urlparse
        app_base = getattr(settings, 'APP_BASE_URL', None)
        if app_base:
            parsed = urlparse(app_base if '://' in app_base else f'https://{app_base}')
            return parsed.netloc, parsed.scheme == 'https'

        canonical = getattr(settings, 'CANONICAL_HOST', None)
        if canonical:
            parsed = urlparse(canonical if '://' in canonical else f'https://{canonical}')
            return parsed.netloc or canonical, parsed.scheme == 'https' or self.request.is_secure()

        allowed = [h for h in settings.ALLOWED_HOSTS if h not in ('*', '')]
        if allowed:
            req_host = self.request.get_host()
            req_host_no_port = req_host.split(':')[0]
            for h in allowed:
                if (h.startswith('.') and req_host_no_port.endswith(h)) or h == req_host_no_port:
                    return req_host, self.request.is_secure()
            return allowed[0], self.request.is_secure()

        return 'localhost:8000', False

    def form_valid(self, form):
        trusted_domain, use_https = self.get_trusted_domain_and_protocol()
        opts = {
            "use_https": use_https,
            "token_generator": self.token_generator,
            "from_email": self.from_email,
            "email_template_name": self.email_template_name,
            "subject_template_name": self.subject_template_name,
            "request": self.request,
            "html_email_template_name": self.html_email_template_name,
            "extra_email_context": self.extra_email_context,
            "domain_override": trusted_domain,
        }
        try:
            form.save(**opts)
        except Exception:
            logger.exception("Falha de envio de email na recuperação de password")
            from django.http import HttpResponseServerError
            return HttpResponseServerError("Ocorreu um erro no servidor de correio ao tentar enviar o email de recuperação.")
        return HttpResponseRedirect(self.get_success_url())
