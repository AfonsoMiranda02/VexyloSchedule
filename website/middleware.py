import urllib.parse
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
            # Rotas protegidas que exigem aceitação explícita dos Termos e Privacidade.
            # Garante correspondência estrita com barra terminal para evitar colisões
            # acidentais de prefixo (ex: /book-something não deve ativar /book/).
            protected_prefixes = (
                '/dashboard/',
                '/book/',
                '/cancel/',
                '/api/submit-testimonial/',
            )

            path = request.path_info
            path_with_slash = path if path.endswith('/') else path + '/'

            if any(path_with_slash.startswith(prefix) for prefix in protected_prefixes):
                profile = getattr(request.user, 'profile', None)
                if not profile or not profile.terms_accepted_at or not profile.privacy_policy_accepted_at:
                    next_url = urllib.parse.quote(request.get_full_path())
                    return redirect(f"{reverse('complete_profile')}?next={next_url}")

        return self.get_response(request)
