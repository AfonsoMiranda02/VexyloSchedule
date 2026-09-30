from django import forms
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Appointment, Service, StaffMember, UserProfile

class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="Primeiro Nome")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=20, required=True, label="Telefone", widget=forms.TextInput(attrs={'type': 'tel'}))
    accept_terms = forms.BooleanField(
        required=True, 
        label=mark_safe("Li e aceito os <a href='/termos-e-condicoes/' target='_blank' rel='noopener noreferrer' class='underline text-blue-600 hover:text-blue-800 transition'>Termos e Condições</a> e a <a href='/politica-de-privacidade/' target='_blank' rel='noopener noreferrer' class='underline text-blue-600 hover:text-blue-800 transition'>Política de Privacidade</a>.")
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("O email é obrigatório.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este email já se encontra registado. Por favor, inicie sessão ou utilize outro email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '').strip().lower()
        if commit:
            user.save()
            now = timezone.now()
            UserProfile.objects.create(
                user=user,
                phone=self.cleaned_data.get('phone', '').strip(),
                terms_accepted_at=now,
                privacy_policy_accepted_at=now
            )
        return user


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['service', 'staff_member', 'date', 'time']
        widgets = {
            'date': forms.TextInput(attrs={'class': 'flatpickr-date w-full p-3 border border-gray-300 rounded-lg focus:ring-primary focus:border-primary bg-white', 'placeholder': 'Selecione a data...'}),
            'time': forms.Select(attrs={'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-primary focus:border-primary bg-white'}),
            'service': forms.Select(attrs={'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-primary focus:border-primary'}),
            'staff_member': forms.Select(attrs={'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-primary focus:border-primary'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar apenas serviços e profissionais ativos para novas marcações
        self.fields['service'].queryset = Service.objects.filter(is_active=True).select_related('category')
        self.fields['staff_member'].queryset = StaffMember.objects.filter(is_active=True)
        self.fields['staff_member'].required = False
        self.fields['staff_member'].empty_label = "Sem preferência (Qualquer profissional disponível)"


class AppointmentAdminForm(forms.ModelForm):
    """
    Formulário do Django Admin para marcações que assegura a integridade das regras
    de negócio (horários de funcionamento, almoço, durações e deteção de colisões com profissionais).
    """
    class Meta:
        model = Appointment
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get('service')
        staff_member = cleaned_data.get('staff_member')
        target_date = cleaned_data.get('date')
        start_time = cleaned_data.get('time')

        if not service or not target_date or not start_time:
            return cleaned_data

        from datetime import datetime, timedelta
        from website.services.booking import BookingService

        # 0. Validação de obrigatoriedade de profissional para novas marcações
        if not self.instance.pk and not staff_member:
            raise forms.ValidationError({'staff_member': "É obrigatório atribuir um profissional para novas marcações."})

        # 0.0 Validação de serviço ativo para novas marcações (ou se alterado em edição)
        if not self.instance.pk and not service.is_active:
            raise forms.ValidationError({'service': "O serviço selecionado já não se encontra ativo para novas marcações."})
        if self.instance.pk and self.instance.service_id != service.id and not service.is_active:
            raise forms.ValidationError({'service': "O novo serviço selecionado não se encontra ativo."})

        # 0.01 Validação de data/hora no passado para novas marcações
        if not self.instance.pk:
            current_tz = timezone.get_current_timezone()
            start_dt_aware = timezone.make_aware(datetime.combine(target_date, start_time), current_tz)
            if start_dt_aware < timezone.now():
                raise forms.ValidationError({'time': "Não é possível realizar novos agendamentos em horários passados."})

        # 0.1 Validação de granularidade de slot (30 minutos)
        if (start_time.minute % BookingService.SLOT_INTERVAL_MINUTES != 0) or start_time.second != 0 or start_time.microsecond != 0:
            raise forms.ValidationError(
                f"Horário de início inválido. As marcações devem iniciar em intervalos de {BookingService.SLOT_INTERVAL_MINUTES} minutos (ex: 09:00, 09:30)."
            )

        duration = self.instance.duration_at_booking or service.duration
        start_dt = datetime.combine(target_date, start_time)
        end_dt = start_dt + timedelta(minutes=duration)

        if end_dt.date() != target_date:
            raise forms.ValidationError("O agendamento ultrapassa o final do dia.")

        # 1. Horário de funcionamento
        is_open, open_time, close_time, lunch_st, lunch_et = BookingService.get_business_hours_for_date(target_date)
        if not is_open:
            raise forms.ValidationError("O estabelecimento está encerrado na data selecionada.")

        open_dt = datetime.combine(target_date, open_time)
        close_dt = datetime.combine(target_date, close_time)

        if start_dt < open_dt or end_dt > close_dt or start_dt >= close_dt:
            raise forms.ValidationError("O agendamento ultrapassa o horário de funcionamento do estabelecimento.")

        if lunch_st and lunch_et:
            lunch_start_dt = datetime.combine(target_date, lunch_st)
            lunch_end_dt = datetime.combine(target_date, lunch_et)
            if start_dt < lunch_end_dt and end_dt > lunch_start_dt:
                raise forms.ValidationError("O horário selecionado coincide com o período de intervalo/almoço.")

        # 2. Verificação de colisão de profissional (excluindo a própria marcação em caso de edição)
        if staff_member:
            if not staff_member.is_active and (not self.instance.pk or self.instance.staff_member_id != staff_member.id):
                raise forms.ValidationError(f"O profissional {staff_member.name} está inativo para novas marcações.")

            collision_qs = Appointment.objects.filter(
                date=target_date,
                staff_member=staff_member
            ).exclude(status='Cancelada')

            if self.instance.pk:
                collision_qs = collision_qs.exclude(pk=self.instance.pk)

            for apt in collision_qs:
                apt_start_dt = datetime.combine(apt.date, apt.time)
                apt_end_dt = (
                    datetime.combine(apt.date, apt.end_time)
                    if apt.end_time
                    else (apt_start_dt + timedelta(minutes=apt.effective_duration))
                )
                if apt_start_dt < end_dt and apt_end_dt > start_dt:
                    raise forms.ValidationError(
                        f"Conflito de horário: O profissional {staff_member.name} já tem uma marcação ({apt.status}) "
                        f"das {apt.time.strftime('%H:%M')} às {apt_end_dt.time().strftime('%H:%M')}."
                    )

        return cleaned_data


class CompleteProfileForm(forms.Form):
    phone = forms.CharField(
        max_length=20, 
        required=True, 
        label="Número de Telefone",
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'placeholder': '9xxxxxxxx',
            'class': 'appearance-none rounded-lg relative block w-full px-4 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm'
        })
    )
    accept_terms = forms.BooleanField(
        required=True,
        label="Declaro que li e aceito os Termos e Condições e a Política de Privacidade do VexyloSchedule.",
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded'
        })
    )

