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
