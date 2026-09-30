from django.shortcuts import redirect
from django.urls import reverse

class TermsAcceptanceMiddleware:
    """
    Garante que utilizadores autenticados (incluindo utilizadores que entram via Google OAuth/social)
    aceitaram explicitamente os Termos e Condições e a Política de Privacidade
    antes de poderem realizar marcações ou aceder à área pessoal.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
            # Rotas protegidas que exigem aceitação explícita dos Termos e Privacidade
            protected_prefixes = (
                '/dashboard',
                '/book',
                '/cancel',
                '/api/submit-testimonial',
            )

            if any(request.path.startswith(prefix) for prefix in protected_prefixes):
                profile = getattr(request.user, 'profile', None)
                if not profile or not profile.terms_accepted_at or not profile.privacy_policy_accepted_at:
                    return redirect(f"{reverse('complete_profile')}?next={request.path}")

        return self.get_response(request)
