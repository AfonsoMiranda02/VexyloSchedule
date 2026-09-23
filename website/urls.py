from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    
    # Autenticação
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    
    # Área de Cliente & Marcações
    path('dashboard/', views.client_dashboard_view, name='dashboard'),
    path('book/', views.book_appointment_view, name='book_appointment'),
    path('cancel/<int:pk>/', views.cancel_appointment_view, name='cancel_appointment'),
    
    # API
    path('api/available-times/', views.get_available_times, name='api_available_times'),
    path('api/admin-dashboard-stats/', views.admin_dashboard_api_view, name='admin_dashboard_stats'),
    path('api/calendar-events/', views.api_calendar_events, name='api_calendar_events'),
    path('api/submit-testimonial/', views.submit_testimonial, name='submit_testimonial'),

    # Legal
    path('politica-de-privacidade/', views.privacy_policy_view, name='privacy_policy'),
    path('termos-e-condicoes/', views.terms_conditions_view, name='terms_conditions'),
]
