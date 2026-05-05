from django import forms
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import UserCreationForm
from .models import Appointment

class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="Primeiro Nome")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=20, required=True, label="Telefone", widget=forms.TextInput(attrs={'type': 'tel'}))
    accept_terms = forms.BooleanField(
        required=True, 
        label=mark_safe("Li e aceito os <a href='/termos-e-condicoes/' class='underline text-blue-600 hover:text-blue-800 transition'>Termos e Condições</a> e a <a href='/politica-de-privacidade/' class='underline text-blue-600 hover:text-blue-800 transition'>Política de Privacidade</a>.")
    )
    class Meta:
        model = User
        fields = ['username', 'first_name', 'email']

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
