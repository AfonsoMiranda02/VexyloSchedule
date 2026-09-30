import functools
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.shortcuts import redirect

from django.conf import settings

def get_client_ip(request):
    """
    Obtém o IP real do cliente.
    Em produção atrás de proxy de confiança (ex: Render com SECURE_PROXY_SSL_HEADER ativo),
    lê HTTP_X_FORWARDED_FOR. Caso contrário, confia em REMOTE_ADDR para evitar spoofing.
    """
    trust_proxy = getattr(settings, 'USE_X_FORWARDED_FOR_RATE_LIMIT', not settings.DEBUG)
    if trust_proxy:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')

def check_rate_limit(key: str, limit: int, period: int) -> bool:
    """
    Verifica se a chave excedeu o limite dentro do período (em segundos).
    Retorna True se for permitido, False se o limite foi ultrapassado.
    """
    cache_key = f"ratelimit:{key}"
    current_count = cache.get(cache_key)
    
    if current_count is None:
        cache.set(cache_key, 1, timeout=period)
        return True
        
    if current_count >= limit:
        return False
        
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, current_count + 1, timeout=period)
    return True

def rate_limit(key_prefix: str, limit: int = 5, period: int = 60, redirect_url: str = None):
    """
    Decorador para limitar taxas de pedidos por IP / utilizador.
    - limit: número máximo de pedidos permitidos
    - period: janela temporal em segundos
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Apenas aplicar em métodos que alteram estado (POST) ou sensíveis
            if request.method == 'POST':
                ip = get_client_ip(request)
                user_id = str(request.user.id) if request.user.is_authenticated else ip
                rate_key = f"{key_prefix}:{user_id}"
                
                allowed = check_rate_limit(rate_key, limit=limit, period=period)
                if not allowed:
                    is_ajax = (
                        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                        request.content_type == 'application/json' or
                        'api' in request.path
                    )
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': 'Demasiadas tentativas num curto período de tempo. Por favor, aguarde alguns instantes.'
                        }, status=429)
                        
                    return HttpResponse(
                        "Demasiadas tentativas. Por favor, aguarde um minuto antes de tentar novamente.",
                        status=429
                    )
                    
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
